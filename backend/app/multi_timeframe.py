"""
多时间框架分析器 (Multi-Timeframe Analyzer)

核心原理:
- 同时分析多个时间周期 (1m, 5m, 15m, 1h, 4h)
- 计算各时间框架的趋势方向和强度
- 生成共振评分: 多个时间框架方向一致 = 高可靠信号
- 只有共振评分达标才允许交易

旧系统参数: 1h(0.4) + 4h(0.35) + 1d(0.25), 最低评分5
新系统升级: 5个时间框架, 更精细的评分机制
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from app.exchange import okx
from app.indicators import calculate_all_indicators


class TrendDirection(Enum):
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


@dataclass
class TimeframeSignal:
    """单个时间框架的信号"""
    timeframe: str
    direction: TrendDirection
    strength: float          # 0-100
    rsi: float
    macd_bullish: bool
    ma_bullish: bool
    volume_ratio: float
    weight: float            # 该时间框架的权重


@dataclass
class ResonanceResult:
    """共振分析结果"""
    score: float             # 共振评分 0-100
    direction: TrendDirection
    signals: List[TimeframeSignal]
    aligned_count: int       # 方向一致的时间框架数
    total_count: int
    description: str
    tradeable: bool          # 是否达到交易条件


class MultiTimeframeAnalyzer:
    """
    多时间框架分析器
    
    时间框架和权重:
    - 1m:  0.10 (噪音大，权重低)
    - 5m:  0.15 (短线信号)
    - 15m: 0.20 (中短线)
    - 1h:  0.30 (核心参考)
    - 4h:  0.25 (趋势确认)
    """
    
    # 时间框架配置: (timeframe, weight, candle_limit)
    TIMEFRAMES = [
        ('1m',  0.10, 200),
        ('5m',  0.15, 200),
        ('15m', 0.20, 100),
        ('1h',  0.30, 100),
        ('4h',  0.25, 60),
    ]
    
    # 共振评分阈值
    MIN_RESONANCE_SCORE = 40   # 最低共振评分 (满分100)
    STRONG_RESONANCE_SCORE = 65  # 强共振评分
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}  # 缓存各时间框架数据
    
    def analyze_timeframe(self, df: pd.DataFrame, timeframe: str, weight: float) -> Optional[TimeframeSignal]:
        """分析单个时间框架"""
        if df.empty or len(df) < 20:
            return None
        
        # 计算指标
        df = calculate_all_indicators(df)
        latest = df.iloc[-1]
        
        # 提取指标值
        rsi = latest.get('rsi', 50)
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        ma5 = latest.get('ma5', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        
        # 计算成交量比率
        if 'volume' in df.columns and len(df) >= 20:
            avg_vol = df['volume'].iloc[-20:].mean()
            cur_vol = df['volume'].iloc[-1]
            volume_ratio = cur_vol / avg_vol if avg_vol > 0 else 1.0
        else:
            volume_ratio = 1.0
        
        # 判断MA排列
        ma_bullish = False
        if ma5 > 0 and ma10 > 0 and ma20 > 0:
            ma_bullish = ma5 > ma10 > ma20
        
        # 判断MACD
        macd_bullish = macd > macd_signal if macd and macd_signal else False
        
        # 综合判断趋势方向
        direction, strength = self._calc_direction(
            rsi=rsi,
            ma_bullish=ma_bullish,
            macd_bullish=macd_bullish,
            volume_ratio=volume_ratio,
            df=df
        )
        
        return TimeframeSignal(
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            rsi=rsi if rsi else 50,
            macd_bullish=macd_bullish,
            ma_bullish=ma_bullish,
            volume_ratio=volume_ratio,
            weight=weight
        )
    
    def _calc_direction(self, rsi, ma_bullish, macd_bullish, volume_ratio, df) -> Tuple[TrendDirection, float]:
        """计算趋势方向和强度"""
        score = 0
        
        # RSI 贡献 (最多 ±30分)
        if rsi:
            if rsi > 70:
                score += 25
            elif rsi > 55:
                score += 15
            elif rsi > 45:
                score += 0
            elif rsi > 30:
                score -= 15
            else:
                score -= 25
        
        # MA排列贡献 (最多 ±30分)
        if ma_bullish:
            score += 30
        else:
            # 检查是否空头排列
            latest = df.iloc[-1]
            ma5 = latest.get('ma5', 0)
            ma10 = latest.get('ma10', 0)
            ma20 = latest.get('ma20', 0)
            if ma5 > 0 and ma10 > 0 and ma20 > 0:
                if ma5 < ma10 < ma20:
                    score -= 30
        
        # MACD贡献 (最多 ±20分)
        if macd_bullish:
            score += 20
        else:
            score -= 10
        
        # 价格动量 (最多 ±20分)
        if len(df) >= 10:
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
            momentum = min(20, max(-20, price_change * 5))
            score += momentum
        
        # 成交量确认
        if volume_ratio > 1.5:
            score = score * 1.2  # 放量时信号增强20%
        
        # 映射到方向
        strength = min(100, max(0, abs(score)))
        if score > 40:
            return TrendDirection.STRONG_UP, strength
        elif score > 15:
            return TrendDirection.UP, strength
        elif score > -15:
            return TrendDirection.NEUTRAL, strength
        elif score > -40:
            return TrendDirection.DOWN, strength
        else:
            return TrendDirection.STRONG_DOWN, strength
    
    def analyze(self, symbol: str) -> Optional[ResonanceResult]:
        """
        对某个币种进行多时间框架分析
        
        返回共振结果
        """
        signals = []
        
        for timeframe, weight, limit in self.TIMEFRAMES:
            try:
                df = okx.fetch_ohlcv(symbol, timeframe, limit=limit)
                if df.empty:
                    continue
                
                signal = self.analyze_timeframe(df, timeframe, weight)
                if signal:
                    signals.append(signal)
            except Exception as e:
                print(f"[MTF] {symbol} {timeframe} 分析失败: {e}")
                continue
        
        if len(signals) < 2:
            return None
        
        return self._calculate_resonance(signals)
    
    def analyze_with_data(self, data_map: Dict[str, pd.DataFrame]) -> Optional[ResonanceResult]:
        """
        用已有数据进行分析（避免重复API调用）
        
        data_map: {'1m': df_1m, '5m': df_5m, ...}
        """
        signals = []
        
        for timeframe, weight, _ in self.TIMEFRAMES:
            if timeframe in data_map:
                df = data_map[timeframe]
                signal = self.analyze_timeframe(df, timeframe, weight)
                if signal:
                    signals.append(signal)
        
        if len(signals) < 2:
            return None
        
        return self._calculate_resonance(signals)
    
    def _calculate_resonance(self, signals: List[TimeframeSignal]) -> ResonanceResult:
        """计算共振评分"""
        
        # 1. 统计各方向的加权得分
        bullish_score = 0
        bearish_score = 0
        neutral_count = 0
        
        for s in signals:
            if s.direction in (TrendDirection.STRONG_UP, TrendDirection.UP):
                bullish_score += s.strength * s.weight
            elif s.direction in (TrendDirection.STRONG_DOWN, TrendDirection.DOWN):
                bearish_score += s.strength * s.weight
            else:
                neutral_count += 1
        
        # 2. 确定主方向
        if bullish_score > bearish_score:
            main_direction = TrendDirection.UP if bullish_score < 50 else TrendDirection.STRONG_UP
            raw_score = bullish_score
        elif bearish_score > bullish_score:
            main_direction = TrendDirection.DOWN if bearish_score < 50 else TrendDirection.STRONG_DOWN
            raw_score = bearish_score
        else:
            main_direction = TrendDirection.NEUTRAL
            raw_score = 0
        
        # 3. 计算方向一致数
        aligned = 0
        for s in signals:
            if main_direction in (TrendDirection.STRONG_UP, TrendDirection.UP):
                if s.direction in (TrendDirection.STRONG_UP, TrendDirection.UP):
                    aligned += 1
            elif main_direction in (TrendDirection.STRONG_DOWN, TrendDirection.DOWN):
                if s.direction in (TrendDirection.STRONG_DOWN, TrendDirection.DOWN):
                    aligned += 1
        
        # 4. 共振加成: 方向一致越多，分数越高
        alignment_ratio = aligned / len(signals)
        resonance_score = raw_score * (0.5 + 0.5 * alignment_ratio)
        resonance_score = min(100, resonance_score)
        
        # 5. 是否可交易
        tradeable = resonance_score >= self.MIN_RESONANCE_SCORE and aligned >= 2
        
        # 6. 生成描述
        tf_str = '/'.join([s.timeframe for s in signals if s.direction == main_direction or 
                          (main_direction in (TrendDirection.STRONG_UP, TrendDirection.UP) and 
                           s.direction in (TrendDirection.STRONG_UP, TrendDirection.UP)) or
                          (main_direction in (TrendDirection.STRONG_DOWN, TrendDirection.DOWN) and 
                           s.direction in (TrendDirection.STRONG_DOWN, TrendDirection.DOWN))])
        
        if tradeable:
            desc = f"共振{aligned}/{len(signals)}({tf_str})，评分{resonance_score:.0f}"
        else:
            desc = f"共振不足{aligned}/{len(signals)}，评分{resonance_score:.0f}，暂不交易"
        
        return ResonanceResult(
            score=resonance_score,
            direction=main_direction,
            signals=signals,
            aligned_count=aligned,
            total_count=len(signals),
            description=desc,
            tradeable=tradeable
        )


# 全局实例
mtf_analyzer = MultiTimeframeAnalyzer()
