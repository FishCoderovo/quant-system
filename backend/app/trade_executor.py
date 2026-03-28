"""
交易执行器 v2.0
新增: 交易所侧止损单管理 (服务端条件单)
- 开仓后自动创建止损单 → 断电后OKX自动执行
- 平仓前自动取消止损单 → 避免重复卖出
- 移动止损时同步更新止损单
- 启动时同步持仓状态 → 检查断电期间止损是否触发
"""
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models import Position, Trade
from app.exchange import okx
from app.risk_manager import RiskManager
from app.config import settings


class TradeExecutor:
    """交易执行器 — 带交易所止损单保护"""
    
    def __init__(self, db: Session):
        self.db = db
        self.risk_manager = RiskManager(db)
    
    # ================================================================
    #  买入 (开仓)
    # ================================================================
    
    def execute_buy(self, 
                    symbol: str,
                    strategy: str,
                    reason: str,
                    entry_price: float,
                    atr: float) -> Optional[Dict]:
        """
        执行买入 + 自动设置交易所止损单
        """
        # 1. 风控检查
        can_trade, daily_pnl = self.risk_manager.check_daily_loss_limit()
        if not can_trade:
            return {'success': False, 'error': f'日亏损限制触发: {daily_pnl:.2f} USDT'}
        
        can_open, position_count = self.risk_manager.check_position_limit()
        if not can_open:
            return {'success': False, 'error': f'持仓数量限制: {position_count}/3'}
        
        can_trade, last_trade_time = self.risk_manager.check_trade_cooldown(symbol)
        if not can_trade:
            return {'success': False, 'error': f'交易冷却期中'}
        
        # 2. 计算止损和目标价
        stop_loss = self.risk_manager.calculate_stop_loss(entry_price, atr)
        take_profit = self.risk_manager.calculate_take_profit(entry_price, stop_loss)
        
        # 3. 检查盈亏比
        if not self.risk_manager.check_risk_reward_ratio(entry_price, stop_loss, take_profit):
            return {'success': False, 'error': '盈亏比不满足要求'}
        
        # 4. 获取账户余额
        try:
            balance = okx.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
        except Exception as e:
            return {'success': False, 'error': f'获取余额失败: {str(e)}'}
        
        # 5. 计算仓位大小
        position_amount = self.risk_manager.calculate_position_size(
            usdt_balance, entry_price, stop_loss
        )
        if position_amount <= 0:
            return {'success': False, 'error': '计算仓位为0'}
        
        # 6. 执行买入
        try:
            limit_price = entry_price * 1.001
            order = okx.create_limit_buy_order(symbol, position_amount, limit_price)
            
            filled_price = order.get('average', entry_price)
            filled_amount = order.get('filled', position_amount)
            value = filled_price * filled_amount
            
        except Exception as e:
            return {'success': False, 'error': f'下单失败: {str(e)}'}
        
        # 7. 🛡️ 创建交易所侧止损单 (关键!)
        sl_order_id = None
        sl_order = okx.create_stop_loss_order(
            symbol=symbol,
            side='sell',            # 做多的止损 = 卖出
            amount=filled_amount,
            trigger_price=stop_loss
        )
        if sl_order:
            sl_order_id = sl_order.get('id')
            print(f"[Executor] 🛡️ 止损单已设置: {symbol} SL={stop_loss:.2f}"
                  f" | OKX Order ID: {sl_order_id}")
        else:
            print(f"[Executor] ⚠️ 止损单设置失败! {symbol} SL={stop_loss:.2f}"
                  f" — 本地监控仍然有效，但断电后无保护")
        
        # 8. 创建持仓记录 (含止损单ID)
        position = Position(
            symbol=symbol,
            side='long',
            amount=filled_amount,
            entry_price=filled_price,
            current_price=filled_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            unrealized_pnl=0,
            strategy=strategy,
            atr=atr,
            stop_loss_order_id=sl_order_id,
        )
        self.db.add(position)
        
        # 9. 创建交易记录
        trade = Trade(
            symbol=symbol,
            side='buy',
            amount=filled_amount,
            price=filled_price,
            value=value,
            strategy=strategy,
            reason=reason
        )
        self.risk_manager.record_trade(trade)
        
        return {
            'success': True,
            'order': order,
            'stop_loss_order_id': sl_order_id,
            'position': {
                'symbol': symbol,
                'amount': filled_amount,
                'entry_price': filled_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'sl_protected': sl_order_id is not None,
            }
        }
    
    # ================================================================
    #  卖出 (平仓)
    # ================================================================
    
    def execute_sell(self,
                     position: Position,
                     reason: str,
                     current_price: float) -> Optional[Dict]:
        """
        执行卖出 — 平仓前先取消交易所止损单
        """
        # 1. 🛡️ 先取消交易所止损单 (避免重复卖出!)
        if position.stop_loss_order_id:
            okx.cancel_stop_loss_order(position.stop_loss_order_id,
                                        position.symbol)
            print(f"[Executor] 取消止损单: {position.stop_loss_order_id}")
        
        try:
            # 2. 执行卖出
            limit_price = current_price * 0.999
            order = okx.create_limit_sell_order(
                position.symbol, position.amount, limit_price)
            
            filled_price = order.get('average', current_price)
            value = filled_price * position.amount
            
            # 3. 计算盈亏
            pnl = (filled_price - position.entry_price) * position.amount
            pnl_pct = ((filled_price - position.entry_price) / 
                       position.entry_price * 100)
            
            # 4. 更新持仓
            position.is_open = False
            position.realized_pnl = pnl
            position.stop_loss_order_id = None
            position.updated_at = datetime.utcnow()
            
            # 5. 创建交易记录
            trade = Trade(
                symbol=position.symbol,
                side='sell',
                amount=position.amount,
                price=filled_price,
                value=value,
                realized_pnl=pnl,
                pnl_pct=pnl_pct,
                strategy=position.strategy,
                reason=reason
            )
            self.risk_manager.record_trade(trade)
            
            return {
                'success': True,
                'order': order,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            }
            
        except Exception as e:
            return {'success': False, 'error': f'卖出失败: {str(e)}'}
    
    # ================================================================
    #  持仓监控 + 移动止损同步
    # ================================================================
    
    def check_and_execute_sells(self, symbol: str,
                                current_price: float) -> List[Dict]:
        """
        检查持仓: 止损/止盈/移动止损
        移动止损时同步更新交易所止损单
        """
        positions = self.db.query(Position).filter(
            Position.symbol == symbol,
            Position.is_open == True
        ).all()
        
        results = []
        for position in positions:
            position.current_price = current_price
            
            # 检查止损
            if self.risk_manager.check_stop_loss_triggered(
                    position, current_price):
                # 本地检测到止损触发 → 先取消交易所止损单再卖
                result = self.execute_sell(position, '止损触发',
                                          current_price)
                results.append(result)
                continue
            
            # 检查止盈
            if self.risk_manager.check_take_profit_triggered(
                    position, current_price):
                result = self.execute_sell(position, '止盈触发',
                                          current_price)
                results.append(result)
                continue
            
            # 更新移动止损
            new_stop = self.risk_manager.update_trailing_stop(
                position, current_price)
            if new_stop:
                # 🛡️ 同步更新交易所止损单
                if position.stop_loss_order_id:
                    new_order = okx.update_stop_loss_order(
                        old_order_id=position.stop_loss_order_id,
                        symbol=position.symbol,
                        side='sell',
                        amount=position.amount,
                        new_trigger_price=new_stop
                    )
                    if new_order:
                        position.stop_loss_order_id = new_order.get('id')
                        print(f"[Executor] 🛡️ 移动止损同步: {symbol}"
                              f" 新SL={new_stop:.2f}")
                    else:
                        print(f"[Executor] ⚠️ 移动止损同步失败:"
                              f" {symbol}")
                
                results.append({
                    'action': 'update_trailing_stop',
                    'symbol': symbol,
                    'new_stop': new_stop,
                    'synced_to_exchange': position.stop_loss_order_id
                                         is not None,
                })
        
        self.db.commit()
        return results
    
    # ================================================================
    #  🔄 启动时同步 (断电恢复)
    # ================================================================
    
    def sync_positions_on_startup(self) -> List[Dict]:
        """
        启动时同步持仓状态
        检查断电期间止损单是否在OKX上已触发
        
        场景: 22:55 断电 → 凌晨BTC暴跌 → OKX止损单触发卖出
              → 06:15 开机 → 本地数据库还以为有持仓
              → 调用此方法同步
        """
        open_positions = self.db.query(Position).filter(
            Position.is_open == True
        ).all()
        
        results = []
        for pos in open_positions:
            sync = okx.sync_position_with_exchange(
                pos.symbol, pos.amount)
            
            if sync['stop_triggered']:
                # 止损单在断电期间触发了!
                print(f"[Sync] 🔔 {pos.symbol} 止损单已在离线期间触发!"
                      f" 本地: {pos.amount}, 交易所: "
                      f"{sync['exchange_amount']}")
                
                # 更新本地数据库
                pos.is_open = False
                pos.stop_loss_order_id = None
                pos.updated_at = datetime.utcnow()
                
                # 尝试从交易历史获取实际平仓价格
                try:
                    ticker = okx.fetch_ticker(pos.symbol)
                    last_price = ticker.get('last', pos.stop_loss)
                    pnl = (pos.stop_loss - pos.entry_price) * pos.amount
                    pos.realized_pnl = pnl
                    
                    trade = Trade(
                        symbol=pos.symbol,
                        side='sell',
                        amount=pos.amount,
                        price=pos.stop_loss,
                        value=pos.stop_loss * pos.amount,
                        realized_pnl=pnl,
                        pnl_pct=(pos.stop_loss - pos.entry_price) / 
                                pos.entry_price * 100,
                        strategy=pos.strategy,
                        reason='[离线] 交易所止损单触发'
                    )
                    self.db.add(trade)
                except Exception as e:
                    print(f"[Sync] 记录离线止损交易失败: {e}")
                
                results.append({
                    'symbol': pos.symbol,
                    'action': 'stop_loss_triggered_offline',
                    'entry_price': pos.entry_price,
                    'stop_loss': pos.stop_loss,
                })
            else:
                # 持仓正常，检查止损单是否还在
                if pos.stop_loss_order_id:
                    triggered = okx.check_stop_loss_triggered(
                        pos.stop_loss_order_id, pos.symbol)
                    if triggered:
                        print(f"[Sync] {pos.symbol} 止损单状态异常，"
                              f"重新创建")
                        new_order = okx.create_stop_loss_order(
                            pos.symbol, 'sell', pos.amount,
                            pos.stop_loss)
                        if new_order:
                            pos.stop_loss_order_id = new_order.get('id')
                
                results.append({
                    'symbol': pos.symbol,
                    'action': 'position_ok',
                    'amount': pos.amount,
                    'stop_loss': pos.stop_loss,
                    'sl_protected': pos.stop_loss_order_id is not None,
                })
        
        self.db.commit()
        return results
    
    # ================================================================
    #  关机前全部平仓
    # ================================================================
    
    def close_all_positions(self, reason: str = '系统关机平仓') -> List[Dict]:
        """
        平掉所有持仓 (关机前调用)
        """
        open_positions = self.db.query(Position).filter(
            Position.is_open == True
        ).all()
        
        results = []
        for pos in open_positions:
            try:
                ticker = okx.fetch_ticker(pos.symbol)
                current_price = ticker.get('last', 0)
                if current_price > 0:
                    result = self.execute_sell(pos, reason,
                                             current_price)
                    results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'symbol': pos.symbol,
                    'error': str(e)
                })
        
        self.db.commit()
        return results
