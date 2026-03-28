"""
交易执行器
"""
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import Position, Trade
from app.exchange import okx
from app.risk_manager import RiskManager
from app.config import settings

class TradeExecutor:
    """交易执行器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.risk_manager = RiskManager(db)
    
    def execute_buy(self, 
                    symbol: str,
                    strategy: str,
                    reason: str,
                    entry_price: float,
                    atr: float) -> Optional[Dict]:
        """
        执行买入
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
        
        # 6. 执行买入 (使用限价单，享受maker费率 0.08% vs 0.15%)
        try:
            # 限价单价格：比当前价高0.1%，确保成交同时享受maker费率
            limit_price = entry_price * 1.001
            order = okx.create_limit_buy_order(symbol, position_amount, limit_price)
            
            # 实际成交价格
            filled_price = order.get('average', entry_price)
            filled_amount = order.get('filled', position_amount)
            value = filled_price * filled_amount
            
            # 7. 创建持仓记录
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
                atr=atr
            )
            self.db.add(position)
            
            # 8. 创建交易记录
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
            
            # 9. 设置交易所止损单
            try:
                okx.set_stop_loss(symbol, filled_amount, stop_loss)
            except Exception as e:
                print(f"设置止损单失败: {e}")
            
            return {
                'success': True,
                'order': order,
                'position': {
                    'symbol': symbol,
                    'amount': filled_amount,
                    'entry_price': filled_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': f'下单失败: {str(e)}'}
    
    def execute_sell(self,
                     position: Position,
                     reason: str,
                     current_price: float) -> Optional[Dict]:
        """
        执行卖出
        """
        try:
            # 1. 执行卖出 (使用限价单，享受maker费率)
            # 限价单价格：比当前价低0.1%，确保成交同时享受maker费率
            limit_price = current_price * 0.999
            order = okx.create_limit_sell_order(position.symbol, position.amount, limit_price)
            
            # 实际成交价格
            filled_price = order.get('average', current_price)
            value = filled_price * position.amount
            
            # 2. 计算盈亏
            pnl = (filled_price - position.entry_price) * position.amount
            pnl_pct = (filled_price - position.entry_price) / position.entry_price * 100
            
            # 3. 更新持仓
            position.is_open = False
            position.realized_pnl = pnl
            position.updated_at = datetime.utcnow()
            
            # 4. 创建交易记录
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
    
    def check_and_execute_sells(self, symbol: str, current_price: float):
        """
        检查持仓并执行必要的卖出
        """
        positions = self.db.query(Position).filter(
            Position.symbol == symbol,
            Position.is_open == True
        ).all()
        
        results = []
        for position in positions:
            # 更新当前价格
            position.current_price = current_price
            
            # 检查止损
            if self.risk_manager.check_stop_loss_triggered(position, current_price):
                result = self.execute_sell(position, '止损触发', current_price)
                results.append(result)
                continue
            
            # 检查止盈
            if self.risk_manager.check_take_profit_triggered(position, current_price):
                result = self.execute_sell(position, '止盈触发', current_price)
                results.append(result)
                continue
            
            # 更新移动止损
            new_stop = self.risk_manager.update_trailing_stop(position, current_price)
            if new_stop:
                results.append({
                    'action': 'update_trailing_stop',
                    'symbol': symbol,
                    'new_stop': new_stop
                })
        
        self.db.commit()
        return results
