"""
OKX 交易所 API 封装
"""
import ccxt
import pandas as pd
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
    
    def fetch_ticker(self, symbol: str) -> Dict:
        """获取最新行情"""
        return self.exchange.fetch_ticker(symbol)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 200) -> pd.DataFrame:
        """
        获取K线数据
        返回 DataFrame: [timestamp, open, high, low, close, volume]
        """
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    
    def fetch_balance(self) -> Dict:
        """获取账户余额"""
        return self.exchange.fetch_balance()
    
    def create_market_buy_order(self, symbol: str, amount: float) -> Dict:
        """市价买入"""
        return self.exchange.create_market_buy_order(symbol, amount)
    
    def create_market_sell_order(self, symbol: str, amount: float) -> Dict:
        """市价卖出"""
        return self.exchange.create_market_sell_order(symbol, amount)
    
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> Dict:
        """限价买入"""
        return self.exchange.create_limit_buy_order(symbol, amount, price)
    
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> Dict:
        """限价卖出"""
        return self.exchange.create_limit_sell_order(symbol, amount, price)
    
    def set_stop_loss(self, symbol: str, amount: float, stop_price: float) -> Dict:
        """设置止损单"""
        # OKX 条件单
        params = {
            'stopLossPrice': stop_price,
            'ordType': 'conditional',
        }
        return self.exchange.create_order(symbol, 'market', 'sell', amount, params=params)
    
    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取持仓"""
        return self.exchange.fetch_positions([symbol] if symbol else None)
    
    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取未完成订单"""
        return self.exchange.fetch_open_orders(symbol)
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """取消订单"""
        return self.exchange.cancel_order(order_id, symbol)

# 全局实例
okx = OKXExchange()
