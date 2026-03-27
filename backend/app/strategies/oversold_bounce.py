"""
超卖反弹策略 (OversoldBounce)
适用: 急跌后的反弹
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal

class OversoldBounceStrategy(Strategy):
    """超卖反弹策略"""
    
    def __init__(self):
        super().__init__("OversoldBounce")
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """评估超卖反弹策略"""
        if not self.enabled:
            return None
        
        if len(df) < 30:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        # 买入条件: RSI < 30 (极度超卖)
        if latest.get('rsi', 50) < 30:
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"RSI极度超卖({latest.get('rsi', 0):.1f})",
                score=65,
                confidence=0.65
            )
        
        # 卖出条件: RSI > 50 (回到中性)
        if latest.get('rsi', 0) > 50:
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"RSI回到中性({latest.get('rsi', 0):.1f})",
                score=50,
                confidence=0.5
            )
        
        return None
