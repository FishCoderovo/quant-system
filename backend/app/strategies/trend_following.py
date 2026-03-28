"""
趋势跟随策略 v3.0 - 双向交易版
支持做多 + 做空
做空逻辑: 做多评分系统的镜像
"""
import pandas as pd
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class TrendFollowingStrategy(Strategy):
    """趋势跟随策略 — 支持双向"""
    
    def __init__(self):
        super().__init__("TrendFollowing")
        self.min_signal_interval = 8
        self.last_signal_idx = -999
    
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        if not self.enabled or len(df) < 30:
            return None
        
        current_idx = len(df) - 1
        if current_idx - self.last_signal_idx < self.min_signal_interval:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        ma5 = latest.get('ma5', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        rsi = latest.get('rsi', 50)
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        vol_ratio = latest.get('volume_ratio', 1.0)
        
        # 5根K线价格变化
        price_5 = 0
        if len(df) >= 10:
            price_5 = (latest['close'] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
        
        # ==================== 做多评估 ====================
        long_score = 0
        long_reasons = []
        
        if ma5 > ma10 > ma20:
            long_score += 30
            long_reasons.append("MA多头排列")
        
        if 45 < rsi < 65:
            long_score += 20
            long_reasons.append(f"RSI{rsi:.0f}")
        elif rsi > 75:
            long_score -= 15
        elif rsi < 35:
            long_score -= 15
        
        if macd > macd_signal:
            long_score += 20
            if prev.get('macd', 0) <= prev.get('macd_signal', 0):
                long_score += 10
                long_reasons.append("MACD金叉")
            else:
                long_reasons.append("MACD多头")
        else:
            long_score -= 10
        
        if vol_ratio > 1.5:
            long_score += 15
            long_reasons.append(f"放量{vol_ratio:.1f}x")
        elif vol_ratio > 1.0:
            long_score += 5
        
        if price_5 > 1:
            long_score += 15
        elif price_5 < -1:
            long_score -= 10
        
        if long_score >= 65:
            self.last_signal_idx = current_idx
            return Signal(
                action='buy', symbol=symbol, strategy=self.name,
                reason=f"趋势做多({long_score}分): {'+'.join(long_reasons[:3])}",
                score=min(90, long_score),
                confidence=min(0.9, long_score / 100)
            )
        
        # ==================== 做空评估 (镜像) ====================
        short_score = 0
        short_reasons = []
        
        # MA空头排列
        if ma5 < ma10 < ma20:
            short_score += 30
            short_reasons.append("MA空头排列")
        
        # RSI偏高区间(35-55)才做空，太低说明已经超卖
        if 35 < rsi < 55:
            short_score += 20
            short_reasons.append(f"RSI{rsi:.0f}")
        elif rsi < 25:
            short_score -= 15  # 极端超卖，不做空
        elif rsi > 70:
            short_score -= 10  # 太高可能是假信号
        
        # MACD空头
        if macd < macd_signal:
            short_score += 20
            if prev.get('macd', 0) >= prev.get('macd_signal', 0):
                short_score += 10
                short_reasons.append("MACD死叉")
            else:
                short_reasons.append("MACD空头")
        else:
            short_score -= 10
        
        # 放量
        if vol_ratio > 1.5:
            short_score += 15
            short_reasons.append(f"放量{vol_ratio:.1f}x")
        elif vol_ratio > 1.0:
            short_score += 5
        
        # 下跌动量
        if price_5 < -1:
            short_score += 15
        elif price_5 > 1:
            short_score -= 10
        
        if short_score >= 65:
            self.last_signal_idx = current_idx
            return Signal(
                action='short', symbol=symbol, strategy=self.name,
                reason=f"趋势做空({short_score}分): {'+'.join(short_reasons[:3])}",
                score=min(90, short_score),
                confidence=min(0.9, short_score / 100)
            )
        
        # ==================== 做多平仓信号 ====================
        sell_score = 0
        sell_reasons = []
        
        if ma5 < ma10:
            sell_score += 30
            sell_reasons.append("MA5<MA10")
        if macd < macd_signal and prev.get('macd', 0) >= prev.get('macd_signal', 0):
            sell_score += 35
            sell_reasons.append("MACD死叉")
        if rsi > 70 and rsi < prev.get('rsi', 0):
            sell_score += 25
            sell_reasons.append(f"RSI{rsi:.0f}回落")
        if rsi > 80:
            sell_score += 30
            sell_reasons.append(f"RSI{rsi:.0f}极端超买")
        if vol_ratio > 1.5 and latest['close'] < prev['close']:
            sell_score += 20
            sell_reasons.append("放量下跌")
        
        if sell_score >= 45:
            self.last_signal_idx = current_idx
            return Signal(
                action='sell', symbol=symbol, strategy=self.name,
                reason=f"趋势卖出({sell_score}分): {'+'.join(sell_reasons[:3])}",
                score=min(85, sell_score),
                confidence=min(0.85, sell_score / 100)
            )
        
        # ==================== 做空平仓信号 ====================
        cover_score = 0
        cover_reasons = []
        
        if ma5 > ma10:
            cover_score += 30
            cover_reasons.append("MA5>MA10")
        if macd > macd_signal and prev.get('macd', 0) <= prev.get('macd_signal', 0):
            cover_score += 35
            cover_reasons.append("MACD金叉")
        if rsi < 30 and rsi > prev.get('rsi', 0):
            cover_score += 25
            cover_reasons.append(f"RSI{rsi:.0f}反弹")
        if rsi < 20:
            cover_score += 30
            cover_reasons.append(f"RSI{rsi:.0f}极端超卖")
        if vol_ratio > 1.5 and latest['close'] > prev['close']:
            cover_score += 20
            cover_reasons.append("放量上涨")
        
        if cover_score >= 45:
            self.last_signal_idx = current_idx
            return Signal(
                action='cover', symbol=symbol, strategy=self.name,
                reason=f"空头平仓({cover_score}分): {'+'.join(cover_reasons[:3])}",
                score=min(85, cover_score),
                confidence=min(0.85, cover_score / 100)
            )
        
        return None
