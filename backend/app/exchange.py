"""
OKX 交易所 API 封装 v2.0
新增: 交易所侧止损单 (服务端条件单)
"""
import ccxt
import pandas as pd
import time
from typing import Optional, List, Dict
from app.config import settings

class OKXExchange:
    """OKX 交易所封装"""
    
    def __init__(self):
        config = {
            'apiKey': settings.OKX_API_KEY,
            'secret': settings.OKX_API_SECRET,
            'password': settings.OKX_PASSPHRASE,
            'enableRateLimit': True,
        }
        
        if settings.OKX_PROXY:
            config['proxies'] = {
                'http': settings.OKX_PROXY,
                'https': settings.OKX_PROXY
            }
        
        self.exchange = ccxt.okx(config)
        
        if settings.OKX_SANDBOX:
            self.exchange.set_sandbox_mode(True)
    
    # ================================================================
    #  行情 & 账户
    # ================================================================
    
    def fetch_ticker(self, symbol: str) -> Dict:
        return self.exchange.fetch_ticker(symbol)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m',
                    limit: int = 200) -> pd.DataFrame:
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    
    def fetch_balance(self) -> Dict:
        return self.exchange.fetch_balance()
    
    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        return self.exchange.fetch_positions([symbol] if symbol else None)
    
    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        return self.exchange.fetch_open_orders(symbol)
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        return self.exchange.cancel_order(order_id, symbol)
    
    # ================================================================
    #  普通下单
    # ================================================================
    
    def create_market_buy_order(self, symbol: str, amount: float) -> Dict:
        return self.exchange.create_market_buy_order(symbol, amount)
    
    def create_market_sell_order(self, symbol: str, amount: float) -> Dict:
        return self.exchange.create_market_sell_order(symbol, amount)
    
    def create_limit_buy_order(self, symbol: str, amount: float,
                               price: float) -> Dict:
        return self.exchange.create_limit_buy_order(symbol, amount, price)
    
    def create_limit_sell_order(self, symbol: str, amount: float,
                                price: float) -> Dict:
        return self.exchange.create_limit_sell_order(symbol, amount, price)
    
    # ================================================================
    #  🛡️ 交易所侧止损单 (服务端条件单)
    #  这些止损单存在OKX服务器上，断电后仍然有效
    # ================================================================
    
    def create_stop_loss_order(self, symbol: str, side: str,
                               amount: float,
                               trigger_price: float) -> Optional[Dict]:
        """
        创建交易所侧止损条件单
        
        Args:
            symbol: 交易对 (如 'BTC/USDT')
            side: 'sell' (平多头止损) 或 'buy' (平空头止损)
            amount: 数量
            trigger_price: 止损触发价格
        
        Returns:
            order dict (含 'id') 或 None
            
        止损单存在OKX服务器上，即使本地断电也会执行。
        """
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                price=None,
                params={
                    'stopPrice': trigger_price,
                    'triggerPxType': 'last',     # 用最新价触发
                    'tdMode': 'cash',            # 现货模式
                }
            )
            print(f"[OKX] ✅ 止损单创建成功: {symbol} {side} @ {trigger_price}"
                  f" | ID: {order.get('id', 'unknown')}")
            return order
        except Exception as e:
            print(f"[OKX] ⚠️ 止损单创建失败(方式1): {e}")
            # 备用方式: 用OKX原生参数
            try:
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=amount,
                    price=None,
                    params={
                        'triggerPrice': str(trigger_price),
                        'orderPx': '-1',         # 市价执行
                        'triggerPxType': 'last',
                    }
                )
                print(f"[OKX] ✅ 止损单创建成功(方式2): {symbol} {side}"
                      f" @ {trigger_price} | ID: {order.get('id', 'unknown')}")
                return order
            except Exception as e2:
                print(f"[OKX] ❌ 止损单创建失败(方式2): {e2}")
                return None
    
    def cancel_stop_loss_order(self, order_id: str,
                                symbol: str) -> bool:
        """
        取消止损条件单
        
        Returns:
            True if cancelled, False otherwise
        """
        if not order_id:
            return False
        try:
            # OKX的条件单/algo单需要 stop=True 参数
            self.exchange.cancel_order(order_id, symbol,
                                       params={'stop': True})
            print(f"[OKX] ✅ 止损单已取消: {order_id}")
            return True
        except Exception as e:
            # 可能已经被触发执行了，不算错误
            print(f"[OKX] ⚠️ 取消止损单: {e} (可能已触发)")
            return False
    
    def update_stop_loss_order(self, old_order_id: str, symbol: str,
                                side: str, amount: float,
                                new_trigger_price: float) -> Optional[Dict]:
        """
        更新止损单 = 取消旧的 + 创建新的
        
        Returns:
            新的 order dict 或 None
        """
        # 1. 取消旧的
        self.cancel_stop_loss_order(old_order_id, symbol)
        time.sleep(0.1)  # 避免限速
        
        # 2. 创建新的
        return self.create_stop_loss_order(symbol, side, amount,
                                           new_trigger_price)
    
    def fetch_algo_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        查询所有未完成的条件单/algo单
        """
        try:
            orders = self.exchange.fetch_open_orders(
                symbol, params={'stop': True})
            return orders
        except Exception as e:
            print(f"[OKX] 查询条件单失败: {e}")
            return []
    
    def check_stop_loss_triggered(self, order_id: str,
                                   symbol: str) -> bool:
        """
        检查止损单是否已被触发执行
        
        Returns:
            True if triggered (no longer pending)
        """
        if not order_id:
            return False
        try:
            order = self.exchange.fetch_order(order_id, symbol,
                                              params={'stop': True})
            status = order.get('status', '')
            # 'closed' = 已触发执行, 'canceled' = 已取消
            return status in ('closed', 'filled', 'triggered')
        except Exception as e:
            # 查不到 = 可能已触发或取消
            print(f"[OKX] 查询止损单状态: {e}")
            return True  # 保守: 假设已触发
    
    def sync_position_with_exchange(self, symbol: str,
                                     local_amount: float) -> Dict:
        """
        同步本地持仓与交易所持仓
        用于断电重启后检查止损单是否在离线期间触发
        
        Returns:
            {'has_position': bool, 'exchange_amount': float, 
             'stop_triggered': bool}
        """
        try:
            balance = self.fetch_balance()
            # 从symbol中提取币种 (BTC/USDT → BTC)
            base_currency = symbol.split('/')[0]
            exchange_amount = balance.get(base_currency, {}).get('total', 0)
            
            # 如果交易所持仓为0但本地记录有持仓 → 止损单已触发
            has_position = exchange_amount > 0
            stop_triggered = (local_amount > 0 and exchange_amount < 
                            local_amount * 0.1)  # 允许10%误差
            
            return {
                'has_position': has_position,
                'exchange_amount': exchange_amount,
                'stop_triggered': stop_triggered,
            }
        except Exception as e:
            print(f"[OKX] 同步持仓失败: {e}")
            return {
                'has_position': True,  # 保守: 假设还有
                'exchange_amount': local_amount,
                'stop_triggered': False,
            }


# 全局实例
okx = OKXExchange()
