"""
趋势跟随策略 (TrendFollowing)
适用: 上涨/强劲上涨趋势
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class TrendFollowingStrategy(Strategy):
    """趋势跟随策略"""
    
    def __init__(self):
        super().__init__("TrendFollowing")
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """评估趋势跟随策略"""
        if not self.enabled:
            return None
        
        if len(df) < 30:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        # 条件1: MA 多头排列 (MA5 > MA10 > MA20)
        ma_aligned = latest.get('ma5', 0) > latest.get('ma10', 0) > latest.get('ma20', 0)
        
        # 条件2: RSI 在 40-70 之间
        rsi_valid = 40 < latest.get('rsi', 0) < 70
        
        # 条件3: 成交量确认 (>80%)
        volume_confirmed = latest.get('volume_ratio', 0) > settings.VOLUME_CONFIRMATION_THRESHOLD
        
        # 条件4: MACD 金叉或多头排列
        macd_bullish = latest.get('macd', 0) > latest.get('macd_signal', 0)
        
        # 买入条件: 满足所有条件
        if ma_aligned and rsi_valid and volume_confirmed and macd_bullish:
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"MA多头+RSI{latest.get('rsi', 0):.1f}+成交量{latest.get('volume_ratio', 0):.2f}x+MACD金叉",
                score=75,
                confidence=0.75
            )
        
        # 卖出条件: RSI > 75 或 MACD死叉
        if latest.get('rsi', 0) > 75:
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"RSI超买({latest.get('rsi', 0):.1f})",
                score=60,
                confidence=0.6
            )
        
        return None
