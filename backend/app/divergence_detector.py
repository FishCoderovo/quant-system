"""
量价背离检测系统 (Volume-Price Divergence Detector)
基于知识库: 2026-03-15-1510-volume-price-divergence.md
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

@dataclass
class DivergenceSignal:
    """背离信号"""
    type: str  # 'top' 顶背离, 'bottom' 底背离
    strength: float  # 强度 0-1
    price_high_low: float  # 价格高点/低点
    volume_at_extreme: float  # 极端价位成交量
    volume_prev: float  # 前次成交量
    confirmation_count: int  # 确认次数
    description: str

class DivergenceDetector:
    """
    量价背离检测器
    
    检测类型:
    1. 顶背离 (Top Divergence): 价格新高 + 成交量递减 = 看跌
    2. 底背离 (Bottom Divergence): 价格新低 + 成交量递减 = 看涨
    
    确认标准:
    - 至少3个价格高点/低点
    - 成交量递减 >30%
    - 多时间框架共振
    """
    
    def __init__(self):
        self.min_swing_points = 3  # 最少摆动点数量
        self.volume_threshold = 0.7  # 成交量递减阈值 70%
        self.lookback_period = 20  # 回望周期
    
    def find_swing_highs(self, df: pd.DataFrame, window: int = 3) -> list:
        """
        找出摆动高点 (Swing Highs)
        """
        highs = []
        for i in range(window, len(df) - window):
            current_high = df['high'].iloc[i]
            # 检查是否局部最高
            is_swing_high = all(
                current_high > df['high'].iloc[i-j] and 
                current_high >= df['high'].iloc[i+j]
                for j in range(1, window+1)
            )
            if is_swing_high:
                highs.append({
                    'index': i,
                    'price': current_high,
                    'volume': df['volume'].iloc[i],
                    'timestamp': df.index[i] if hasattr(df.index, 'iloc') else i
                })
        return highs
    
    def find_swing_lows(self, df: pd.DataFrame, window: int = 3) -> list:
        """
        找出摆动低点 (Swing Lows)
        """
        lows = []
        for i in range(window, len(df) - window):
            current_low = df['low'].iloc[i]
            # 检查是否局部最低
            is_swing_low = all(
                current_low < df['low'].iloc[i-j] and 
                current_low <= df['low'].iloc[i+j]
                for j in range(1, window+1)
            )
            if is_swing_low:
                lows.append({
                    'index': i,
                    'price': current_low,
                    'volume': df['volume'].iloc[i],
                    'timestamp': df.index[i] if hasattr(df.index, 'iloc') else i
                })
        return lows
    
    def detect_top_divergence(self, df: pd.DataFrame) -> Optional[DivergenceSignal]:
        """
        检测顶背离
        
        条件:
        1. 价格连续创新高 (至少3个高点)
        2. 对应成交量递减 (>30%)
        3. 最后一个高点RSI < 70 (非极度超买)
        """
        swing_highs = self.find_swing_highs(df)
        
        if len(swing_highs) < self.min_swing_points:
            return None
        
        # 取最近3个高点
        recent_highs = swing_highs[-self.min_swing_points:]
        
        # 检查价格是否创新高
        price_increasing = all(
            recent_highs[i]['price'] > recent_highs[i-1]['price']
            for i in range(1, len(recent_highs))
        )
        
        if not price_increasing:
            return None
        
        # 检查成交量是否递减
        volume_decreasing = all(
            recent_highs[i]['volume'] < recent_highs[i-1]['volume'] * self.volume_threshold
            for i in range(1, len(recent_highs))
        )
        
        if not volume_decreasing:
            return None
        
        # 计算背离强度
        volume_drop = 1 - (recent_highs[-1]['volume'] / recent_highs[0]['volume'])
        strength = min(volume_drop, 1.0)
        
        return DivergenceSignal(
            type='top',
            strength=strength,
            price_high_low=recent_highs[-1]['price'],
            volume_at_extreme=recent_highs[-1]['volume'],
            volume_prev=recent_highs[0]['volume'],
            confirmation_count=len(recent_highs),
            description=f"顶背离: 价格新高 {recent_highs[-1]['price']:.2f} 但成交量下降 {volume_drop*100:.1f}%"
        )
    
    def detect_bottom_divergence(self, df: pd.DataFrame) -> Optional[DivergenceSignal]:
        """
        检测底背离
        
        条件:
        1. 价格连续创新低 (至少3个低点)
        2. 对应成交量递减 (>30%)
        """
        swing_lows = self.find_swing_lows(df)
        
        if len(swing_lows) < self.min_swing_points:
            return None
        
        # 取最近3个低点
        recent_lows = swing_lows[-self.min_swing_points:]
        
        # 检查价格是否创新低
        price_decreasing = all(
            recent_lows[i]['price'] < recent_lows[i-1]['price']
            for i in range(1, len(recent_lows))
        )
        
        if not price_decreasing:
            return None
        
        # 检查成交量是否递减
        volume_decreasing = all(
            recent_lows[i]['volume'] < recent_lows[i-1]['volume'] * self.volume_threshold
            for i in range(1, len(recent_lows))
        )
        
        if not volume_decreasing:
            return None
        
        # 计算背离强度
        volume_drop = 1 - (recent_lows[-1]['volume'] / recent_lows[0]['volume'])
        strength = min(volume_drop, 1.0)
        
        return DivergenceSignal(
            type='bottom',
            strength=strength,
            price_high_low=recent_lows[-1]['price'],
            volume_at_extreme=recent_lows[-1]['volume'],
            volume_prev=recent_lows[0]['volume'],
            confirmation_count=len(recent_lows),
            description=f"底背离: 价格新低 {recent_lows[-1]['price']:.2f} 但成交量下降 {volume_drop*100:.1f}%"
        )
    
    def detect_divergence(self, df: pd.DataFrame) -> Optional[DivergenceSignal]:
        """
        综合检测背离信号
        
        返回最强信号 (如果有)
        """
        if len(df) < self.lookback_period:
            return None
        
        top_div = self.detect_top_divergence(df)
        bottom_div = self.detect_bottom_divergence(df)
        
        # 返回强度更高的信号
        if top_div and bottom_div:
            return top_div if top_div.strength >= bottom_div.strength else bottom_div
        elif top_div:
            return top_div
        elif bottom_div:
            return bottom_div
        
        return None
    
    def get_divergence_score(self, df: pd.DataFrame) -> Tuple[float, str]:
        """
        获取背离评分
        
        返回: (分数 -100~100, 描述)
        - 正值 = 看涨背离 (底背离)
        - 负值 = 看跌背离 (顶背离)
        - 0 = 无背离
        """
        signal = self.detect_divergence(df)
        
        if signal is None:
            return 0, "无背离"
        
        if signal.type == 'top':
            score = -int(signal.strength * 100)
            return score, signal.description
        else:  # bottom
            score = int(signal.strength * 100)
            return score, signal.description

# 全局实例
divergence_detector = DivergenceDetector()
