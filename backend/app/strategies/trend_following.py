"""
趋势跟随策略 v2.0 - 改进版
适用: 上涨趋势
改进:
1. 更完善的卖出逻辑（MA死叉 + MACD死叉 + RSI超买）
2. 趋势强度评分，而不是简单的条件叠加
3. 信号冷却期
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class TrendFollowingStrategy(Strategy):
    """趋势跟随策略 - 改进版"""
    
    def __init__(self):
        super().__init__("TrendFollowing")
        self.min_signal_interval = 8   # 从4提高到8，减少交易频率
        self.last_signal_idx = -999
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        if not self.enabled or len(df) < 30:
            return None
        
        current_idx = len(df) - 1
        if current_idx - self.last_signal_idx < self.min_signal_interval:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ========== 趋势评分系统 v2 ==========
        score = 0
        reasons = []
        
        # 1. MA排列 (+30分)
        ma5 = latest.get('ma5', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        
        if ma5 > ma10 > ma20:
            score += 30
            reasons.append("MA多头排列")
        elif ma5 < ma10 < ma20:
            score -= 30
            reasons.append("MA空头排列")
        
        # 2. RSI (+20分)
        rsi = latest.get('rsi', 50)
        if 45 < rsi < 65:
            score += 20  # 健康区间
            reasons.append(f"RSI{rsi:.0f}")
        elif rsi > 75:
            score -= 15  # 超买
        elif rsi < 35:
            score -= 15  # 超卖
        
        # 3. MACD (+20分)
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        if macd > macd_signal:
            score += 20
            if prev.get('macd', 0) <= prev.get('macd_signal', 0):
                score += 10
                reasons.append("MACD金叉")
            else:
                reasons.append("MACD多头")
        else:
            score -= 10
        
        # 4. 成交量确认 (+15分)
        vol_ratio = latest.get('volume_ratio', 1.0)
        if vol_ratio > 1.5:
            score += 15
            reasons.append(f"放量{vol_ratio:.1f}x")
        elif vol_ratio > 1.0:
            score += 5
        
        # 5. 价格动量 (+15分)
        if len(df) >= 10:
            price_5 = (latest['close'] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            if price_5 > 1:
                score += 15
            elif price_5 < -1:
                score -= 10
        
        # ========== 买入决策 ==========
        if score >= 65:
            self.last_signal_idx = current_idx
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"趋势买入({score}分): {'+'.join(reasons[:3])}",
                score=min(90, score),
                confidence=min(0.9, score / 100)
            )
        
        # ========== 卖出决策（改进：多条件）==========
        sell_score = 0
        sell_reasons = []
        
        # MA死叉
        if ma5 < ma10:
            sell_score += 30
            sell_reasons.append("MA5<MA10")
        
        # MACD死叉
        if macd < macd_signal and prev.get('macd', 0) >= prev.get('macd_signal', 0):
            sell_score += 35
            sell_reasons.append("MACD死叉")
        
        # RSI超买回落
        if rsi > 70 and rsi < prev.get('rsi', 0):
            sell_score += 25
            sell_reasons.append(f"RSI{rsi:.0f}回落")
        
        # 极端超买
        if rsi > 80:
            sell_score += 30
            sell_reasons.append(f"RSI{rsi:.0f}极端超买")
        
        # 放量下跌
        if vol_ratio > 1.5 and latest['close'] < prev['close']:
            sell_score += 20
            sell_reasons.append("放量下跌")
        
        if sell_score >= 45:
            self.last_signal_idx = current_idx
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"趋势卖出({sell_score}分): {'+'.join(sell_reasons[:3])}",
                score=min(85, sell_score),
                confidence=min(0.85, sell_score / 100)
            )
        
        return None
