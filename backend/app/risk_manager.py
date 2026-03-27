"""
风控系统
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Position, Trade, DailyStats
from app.config import settings

class RiskManager:
    """风险管理器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_daily_loss_limit(self) -> Tuple[bool, float]:
        """
        检查日亏损限制
        返回: (是否允许交易, 当日累计盈亏)
        """
        today = datetime.now().strftime('%Y-%m-%d')
        daily_stats = self.db.query(DailyStats).filter(DailyStats.date == today).first()
        
        if daily_stats is None:
            return True, 0.0
        
        if daily_stats.total_pnl < -settings.DAILY_LOSS_LIMIT:
            return False, daily_stats.total_pnl
        
        return True, daily_stats.total_pnl
    
    def check_position_limit(self) -> Tuple[bool, int]:
        """
        检查持仓数量限制
        返回: (是否允许开新仓, 当前持仓数)
        """
        open_positions = self.db.query(Position).filter(Position.is_open == True).count()
        return open_positions < 3, open_positions  # 最多3个持仓
    
    def check_trade_cooldown(self, symbol: str) -> Tuple[bool, Optional[datetime]]:
        """
        检查交易冷却期
        返回: (是否冷却完成, 最后一笔交易时间)
        """
        last_trade = self.db.query(Trade).filter(
            Trade.symbol == symbol
        ).order_by(Trade.created_at.desc()).first()
        
        if last_trade is None:
            return True, None
        
        cooldown_end = last_trade.created_at + timedelta(minutes=settings.TRADE_COOLDOWN_MIN)
        return datetime.utcnow() >= cooldown_end, last_trade.created_at
    
    def calculate_position_size(self, 
                                 account_value: float,
                                 entry_price: float,
                                 stop_loss_price: float) -> float:
        """
        基于2%风险法则计算仓位大小
        """
        # 风险金额 (账户的2%)
        risk_amount = account_value * settings.MAX_SINGLE_RISK_PCT
        
        # 止损距离 (%)
        stop_distance = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_distance == 0:
            return 0
        
        # 计算仓位
        position_value = risk_amount / stop_distance
        
        # 限制最大仓位 (单次最大70%)
        max_position = account_value * settings.MAX_POSITION_PCT
        position_value = min(position_value, max_position)
        
        # 转换为币的数量
        position_amount = position_value / entry_price
        
        return position_amount
    
    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        计算 ATR 动态止损价
        """
        return entry_price - (2 * atr)
    
    def calculate_take_profit(self, entry_price: float, stop_loss_price: float) -> float:
        """
        计算目标价 (盈亏比 2:1)
        """
        risk = entry_price - stop_loss_price
        return entry_price + (risk * 2)
    
    def check_risk_reward_ratio(self, 
                                 entry_price: float,
                                 stop_loss_price: float,
                                 take_profit_price: float) -> bool:
        """
        检查盈亏比是否满足要求 (≥0.8:1)
        """
        risk = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        
        if risk == 0:
            return False
        
        ratio = reward / risk
        return ratio >= settings.MIN_RISK_REWARD_RATIO
    
    def update_trailing_stop(self, position: Position, current_price: float) -> Optional[float]:
        """
        更新移动止损
        """
        if position.current_price is None or current_price > position.current_price:
            # 价格创新高，更新移动止损
            atr = position.atr if position.atr else current_price * 0.02
            new_stop = current_price - (2 * atr)
            
            if new_stop > position.stop_loss:
                position.stop_loss = new_stop
                self.db.commit()
                return new_stop
        
        return None
    
    def check_stop_loss_triggered(self, position: Position, current_price: float) -> bool:
        """
        检查是否触发止损
        """
        if position.stop_loss and current_price <= position.stop_loss:
            return True
        return False
    
    def check_take_profit_triggered(self, position: Position, current_price: float) -> bool:
        """
        检查是否触发止盈
        """
        if position.take_profit and current_price >= position.take_profit:
            return True
        return False
    
    def record_trade(self, trade: Trade):
        """记录交易并更新日统计"""
        self.db.add(trade)
        
        # 更新日统计
        today = datetime.now().strftime('%Y-%m-%d')
        daily_stats = self.db.query(DailyStats).filter(DailyStats.date == today).first()
        
        if daily_stats is None:
            daily_stats = DailyStats(date=today)
            self.db.add(daily_stats)
        
        daily_stats.trade_count += 1
        if trade.realized_pnl:
            daily_stats.total_pnl += trade.realized_pnl
            if trade.realized_pnl > 0:
                daily_stats.win_count += 1
            else:
                daily_stats.loss_count += 1
        
        self.db.commit()
