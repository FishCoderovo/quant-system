"""
均值回归策略 (MeanReversion)
适用: 震荡市场
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class MeanReversionStrategy(Strategy):
    """均值回归策略"""
    
    def __init__(self):
        super().__init__("MeanReversion")
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """评估均值回归策略"""
        if not self.enabled:
            return None
        
        if len(df) < 30:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        # 条件1: RSI < 50 (超卖区域)
        rsi_oversold = latest.get('rsi', 50) < 50
        
        # 条件2: 布林带位置 < 45% (接近下轨)
        bb_low = latest.get('bb_position', 0.5) < 0.45
        
        # 条件3: 成交量确认 (>80%)
        volume_confirmed = latest.get('volume_ratio', 0) > settings.VOLUME_CONFIRMATION_THRESHOLD
        
        # 买入条件
        if rsi_oversold and bb_low and volume_confirmed:
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"RSI{latest.get('rsi', 0):.1f}+BB下轨{latest.get('bb_position', 0)*100:.1f}%+成交量{latest.get('volume_ratio', 0):.2f}x",
                score=70,
                confidence=0.7
            )
        
        # 卖出条件: RSI > 70 或 BB位置 > 85%
        if latest.get('rsi', 0) > 70 or latest.get('bb_position', 0) > 0.85:
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"RSI{latest.get('rsi', 0):.1f}/BB位置{latest.get('bb_position', 0)*100:.1f}%",
                score=60,
                confidence=0.6
            )
        
        return None
