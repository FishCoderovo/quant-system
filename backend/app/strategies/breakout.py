"""
突破策略 (Breakout)
适用: 高波动市场
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class BreakoutStrategy(Strategy):
    """突破策略"""
    
    def __init__(self):
        super().__init__("Breakout")
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """评估突破策略"""
        if not self.enabled:
            return None
        
        if len(df) < 30:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 条件1: 价格突破布林带上轨
        price_above_bb = latest['close'] > latest.get('bb_upper', float('inf'))
        prev_below_bb = prev['close'] <= prev.get('bb_upper', 0)
        bb_breakout = price_above_bb and prev_below_bb
        
        # 条件2: 价格突破 R1 阻力位 (>0.5%)
        r1_breakout = latest['close'] > latest.get('r1', 0) * 1.005
        
        # 条件3: MACD 金叉或多头排列
        macd_bullish = latest.get('macd', 0) > latest.get('macd_signal', 0)
        macd_prev_bearish = prev.get('macd', 0) <= prev.get('macd_signal', 0)
        macd_crossover = macd_bullish and macd_prev_bearish
        
        # 条件4: RSI > 50
        rsi_valid = latest.get('rsi', 0) > 50
        
        # 条件5: 成交量确认 (㺀%)
        volume_confirmed = latest.get('volume_ratio', 0) > settings.VOLUME_CONFIRMATION_THRESHOLD
        
        # 买入条件: (BB突破 或 R1突破) + MACD金叉 + RSI 㹐 + 成交量确认
        breakout_condition = (bb_breakout or r1_breakout) and macd_crossover and rsi_valid and volume_confirmed
        
        if breakout_condition:
            reason = []
            if bb_breakout:
                reason.append("BB上轨突破")
            if r1_breakout:
                reason.append("R1突破")
            reason.append(f"MACD金叉+RSI{latest.get('rsi', 0):.1f}+成交量{latest.get('volume_ratio', 0):.2f}x")
            
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason="+".join(reason),
                score=80,
                confidence=0.8
            )
        
        # 卖出条件: MACD死叉
        macd_bearish = latest.get('macd', 0) < latest.get('macd_signal', 0)
        macd_prev_bullish = prev.get('macd', 0) > prev.get('macd_signal', 0)
        macd_crossdown = macd_bearish and macd_prev_bullish
        
        if macd_crossdown:
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason="MACD死叉",
                score=55,
                confidence=0.55
            )
        
        return None
