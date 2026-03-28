"""
均值回归策略 v2.0 - 修复版
适用: 震荡市场
改进:
1. 提高买入门槛（RSI<40 + BB<35%），降低信号频率
2. 增加卖出条件，平衡买卖
3. 添加趋势过滤（避免下跌趋势中接飞刀）
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class MeanReversionStrategy(Strategy):
    """均值回归策略 - 修复版"""
    
    def __init__(self):
        super().__init__("MeanReversion")
        self.min_signal_interval = 10  # 从6提高到10，减少交易频率
        self.last_signal_idx = -999
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """评估均值回归策略 - 修复版"""
        if not self.enabled:
            return None
        
        if len(df) < 30:
            return None
        
        current_idx = len(df) - 1
        
        # 检查冷却期
        if current_idx - self.last_signal_idx < self.min_signal_interval:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # ========== 趋势过滤 ==========
        # 如果MA空头排列，禁止买入（避免下跌趋势接飞刀）
        ma_bearish = latest.get('ma5', 0) < latest.get('ma10', 0) < latest.get('ma20', 0)
        
        # 如果20周期跌幅>5%，认为是下跌趋势
        price_20_ago = df['close'].iloc[-20] if len(df) >= 20 else df['close'].iloc[0]
        trend_20 = (latest['close'] - price_20_ago) / price_20_ago
        is_downtrend = trend_20 < -0.05
        
        # ========== 买入条件（提高门槛）==========
        # 原：RSI<50 + BB<45% → 新：RSI<40 + BB<35% + 成交量>1.2x + 非下跌趋势
        rsi_deep_oversold = latest.get('rsi', 50) < 40  # 从50降到40
        bb_very_low = latest.get('bb_position', 0.5) < 0.35  # 从45%降到35%
        volume_strong = latest.get('volume_ratio', 0) > 1.2  # 从0.8提高到1.2
        
        # 附加：价格开始企稳（当前close > 前一根low）
        price_stabilizing = latest['close'] > prev['low']
        
        if rsi_deep_oversold and bb_very_low and volume_strong and not is_downtrend and price_stabilizing:
            self.last_signal_idx = current_idx
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"均值回归买入: RSI{latest.get('rsi', 0):.1f}+BB{latest.get('bb_position', 0)*100:.1f}%+放量{latest.get('volume_ratio', 0):.2f}x",
                score=75,
                confidence=0.75
            )
        
        # ========== 卖出条件（增加）==========
        # 原：RSI>70 或 BB>85% → 新：RSI>65 或 BB>75%（降低门槛，增加卖出信号）
        rsi_overbought = latest.get('rsi', 0) > 65  # 从70降到65
        bb_high = latest.get('bb_position', 0) > 0.75  # 从85%降到75%
        
        # 附加：从高点回落（当前close < 前一根high且RSI下降）
        pullback = latest['close'] < prev['high'] and latest.get('rsi', 0) < prev.get('rsi', 0)
        
        if (rsi_overbought or bb_high) and pullback:
            self.last_signal_idx = current_idx
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"均值回归卖出: RSI{latest.get('rsi', 0):.1f}/BB{latest.get('bb_position', 0)*100:.1f}%+回落",
                score=65,
                confidence=0.65
            )
        
        return None
