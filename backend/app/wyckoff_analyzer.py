"""
Wyckoff 市场周期分析器
基于知识库: 2026-03-18-1715-wyckoff-market-cycles.md

识别市场四阶段:
1. 积累期 (Accumulation) - 底部吸筹
2. 上升期 (Markup) - 趋势上涨
3. 派发期 (Distribution) - 顶部出货
4. 下降期 (Markdown) - 趋势下跌
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from enum import Enum
from dataclasses import dataclass

class WyckoffPhase(Enum):
    """Wyckoff 阶段"""
    ACCUMULATION = "积累期"
    MARKUP = "上升期"
    DISTRIBUTION = "派发期"
    MARKDOWN = "下降期"
    UNKNOWN = "未知"

class WyckoffEvent(Enum):
    """Wyckoff 关键事件"""
    PS = "Preliminary Support"  # 初步支撑
    SC = "Selling Climax"  # 恐慌抛售
    AR = "Automatic Rally"  # 自然反弹
    ST = "Secondary Test"  # 二次测试
    SPRING = "Spring"  # 弹簧测试
    SOS = "Sign of Strength"  # 强势信号
    UPTRUST = "Upthrust"  # 上冲回落
    LPS = "Last Point of Support"  # 最后支撑点

@dataclass
class WyckoffAnalysis:
    """Wyckoff 分析结果"""
    phase: WyckoffPhase
    confidence: float  # 置信度 0-1
    event: Optional[WyckoffEvent]  # 当前事件
    description: str
    support_level: Optional[float]  # 支撑位
    resistance_level: Optional[float]  # 阻力位
    volume_trend: str  # 成交量趋势
    recommendation: str  # 交易建议

class WyckoffAnalyzer:
    """
    Wyckoff 市场周期分析器
    
    核心原理:
    - 识别市场四阶段循环
    - 检测关键 Wyckoff 事件
    - 提供阶段-specific 交易建议
    """
    
    def __init__(self):
        self.lookback = 50  # 回望周期
        self.volume_ma_period = 20
    
    def calculate_volume_profile(self, df: pd.DataFrame) -> Dict:
        """
        计算成交量分布
        
        返回:
        - POC: 控制点 (成交量最大价位)
        - HVN: 高成交量区域
        - LVN: 低成交量区域
        """
        # 按价格区间分组计算成交量
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # 创建10个价格区间
        bins = np.linspace(price_min, price_max, 11)
        df['price_zone'] = pd.cut(df['close'], bins=bins)
        
        volume_profile = df.groupby('price_zone')['volume'].sum()
        
        # POC (Point of Control)
        poc_zone = volume_profile.idxmax()
        poc_price = (poc_zone.left + poc_zone.right) / 2
        
        # HVN (High Volume Nodes) - 成交量 > 平均
        avg_volume = volume_profile.mean()
        hvn_zones = volume_profile[volume_profile > avg_volume * 1.5]
        
        # LVN (Low Volume Nodes) - 成交量 < 平均
        lvn_zones = volume_profile[volume_profile < avg_volume * 0.5]
        
        return {
            'poc': poc_price,
            'hvn': [(z.left, z.right) for z in hvn_zones.index],
            'lvn': [(z.left, z.right) for z in lvn_zones.index],
            'volume_profile': volume_profile
        }
    
    def detect_selling_climax(self, df: pd.DataFrame) -> Optional[Tuple[int, float]]:
        """
        检测恐慌抛售 (Selling Climax)
        
        特征:
        - 长阴线
        - 成交量放大 (3倍以上)
        - 价格快速下跌
        """
        if len(df) < 5:
            return None
        
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        
        for i in range(-10, 0):  # 检查最近10根K线
            if abs(i) > len(df):
                continue
                
            candle = df.iloc[i]
            body = abs(candle['close'] - candle['open'])
            range_ = candle['high'] - candle['low']
            
            # 长阴线: 收盘 < 开盘，且实体较大
            is_long_red = candle['close'] < candle['open'] and body > range_ * 0.6
            
            # 成交量放大
            volume_spike = candle['volume'] > avg_volume * 3
            
            if is_long_red and volume_spike:
                return i, candle['low']
        
        return None
    
    def detect_spring(self, df: pd.DataFrame, support_level: float) -> bool:
        """
        检测弹簧测试 (Spring)
        
        特征:
        - 价格短暂跌破支撑位
        - 但快速收回 (收盘价在支撑之上)
        - 成交量可能放大 (清洗止损)
        """
        if len(df) < 3:
            return False
        
        # 检查最近3根K线
        for i in range(-3, 0):
            if abs(i) > len(df):
                continue
                
            candle = df.iloc[i]
            
            # 跌破支撑
            broke_support = candle['low'] < support_level * 0.995
            
            # 但收盘收回
            recovered = candle['close'] > support_level
            
            if broke_support and recovered:
                return True
        
        return False
    
    def detect_upthrust(self, df: pd.DataFrame, resistance_level: float) -> bool:
        """
        检测上冲回落 (Upthrust)
        
        特征:
        - 价格短暂突破阻力位
        - 但快速回落 (收盘价在阻力之下)
        - 可能伴随成交量放大
        """
        if len(df) < 3:
            return False
        
        for i in range(-3, 0):
            if abs(i) > len(df):
                continue
                
            candle = df.iloc[i]
            
            # 突破阻力
            broke_resistance = candle['high'] > resistance_level * 1.005
            
            # 但收盘回落
            fell_back = candle['close'] < resistance_level
            
            if broke_resistance and fell_back:
                return True
        
        return False
    
    def analyze_phase(self, df: pd.DataFrame) -> WyckoffAnalysis:
        """
        分析当前 Wyckoff 阶段
        """
        if len(df) < self.lookback:
            return WyckoffAnalysis(
                phase=WyckoffPhase.UNKNOWN,
                confidence=0,
                event=None,
                description="数据不足",
                support_level=None,
                resistance_level=None,
                volume_trend="unknown",
                recommendation="观望"
            )
        
        # 计算基础指标
        price_change_20 = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
        price_change_50 = (df['close'].iloc[-1] - df['close'].iloc[-50]) / df['close'].iloc[-50]
        
        volume_ma = df['volume'].rolling(self.volume_ma_period).mean()
        current_volume = df['volume'].iloc[-1]
        volume_trend = "increasing" if current_volume > volume_ma.iloc[-1] else "decreasing"
        
        # 计算成交量分布
        vol_profile = self.calculate_volume_profile(df)
        poc = vol_profile['poc']
        
        # 检测关键事件
        sc = self.detect_selling_climax(df)
        spring = self.detect_spring(df, poc * 0.95)
        upthrust = self.detect_upthrust(df, poc * 1.05)
        
        # 阶段判定逻辑
        phase = WyckoffPhase.UNKNOWN
        confidence = 0.5
        event = None
        description = ""
        recommendation = "观望"
        
        # 积累期判定
        if price_change_50 < -0.15 and price_change_20 > -0.05:
            phase = WyckoffPhase.ACCUMULATION
            confidence = 0.6
            
            if sc:
                event = WyckoffEvent.SC
                description = "恐慌抛售后出现，可能形成底部"
                recommendation = "观察二次测试，准备入场"
                confidence = 0.75
            elif spring:
                event = WyckoffEvent.SPRING
                description = "弹簧测试 - 最佳入场点"
                recommendation = "做多入场"
                confidence = 0.85
            else:
                description = "底部震荡，主力吸筹中"
                recommendation = "等待Spring测试或SOS突破"
        
        # 上升期判定
        elif price_change_20 > 0.05 and price_change_50 > 0:
            phase = WyckoffPhase.MARKUP
            confidence = 0.7
            
            # 检查是否突破POC
            if df['close'].iloc[-1] > poc * 1.05:
                event = WyckoffEvent.SOS
                description = "强势突破，上升趋势确认"
                recommendation = "持有或回调加仓"
                confidence = 0.8
            else:
                description = "上升趋势中"
                recommendation = "持有多单，移动止损"
        
        # 派发期判定
        elif price_change_50 > 0.15 and price_change_20 < 0.05:
            phase = WyckoffPhase.DISTRIBUTION
            confidence = 0.6
            
            if upthrust:
                event = WyckoffEvent.UPTRUST
                description = "上冲回落 - 顶部信号"
                recommendation = "减仓或做空"
                confidence = 0.8
            else:
                description = "顶部震荡，主力出货中"
                recommendation = "减仓，等待确认"
        
        # 下降期判定
        elif price_change_20 < -0.05 and price_change_50 < 0:
            phase = WyckoffPhase.MARKDOWN
            confidence = 0.7
            description = "下降趋势中"
            recommendation = "观望或做空"
        
        return WyckoffAnalysis(
            phase=phase,
            confidence=confidence,
            event=event,
            description=description,
            support_level=poc * 0.95,
            resistance_level=poc * 1.05,
            volume_trend=volume_trend,
            recommendation=recommendation
        )
    
    def get_phase_score(self, df: pd.DataFrame) -> Tuple[int, str]:
        """
        获取阶段评分
        
        返回: (分数 -100~100, 描述)
        - 正值 = 看涨 (积累期/上升期)
        - 负值 = 看跌 (派发期/下降期)
        """
        analysis = self.analyze_phase(df)
        
        phase_scores = {
            WyckoffPhase.ACCUMULATION: 60,
            WyckoffPhase.MARKUP: 80,
            WyckoffPhase.DISTRIBUTION: -60,
            WyckoffPhase.MARKDOWN: -80,
            WyckoffPhase.UNKNOWN: 0
        }
        
        base_score = phase_scores.get(analysis.phase, 0)
        weighted_score = int(base_score * analysis.confidence)
        
        return weighted_score, f"[{analysis.phase.value}] {analysis.description}"

# 全局实例
wyckoff_analyzer = WyckoffAnalyzer()
