"""
资金费率策略 (Funding Rate Strategy)
基于知识库: 2026-03-17-2215-funding-rate-perpetual-futures.md

功能:
1. 资金费率趋势交易 (极端费率 = 反转信号)
2. 资金费率套利 (永续对冲收费率)
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FundingRateSignal:
    """资金费率信号"""
    type: str  # 'arbitrage', 'trend_reversal'
    direction: str  # 'long', 'short'
    strength: float  # 0-1
    funding_rate: float  # 当前资金费率
    annualized_rate: float  # 年化费率
    description: str
    expected_profit: float  # 预期收益

class FundingRateStrategy:
    """
    资金费率策略
    
    原理:
    - 资金费率 > +0.1%: 极度贪婪，做空信号 + 套利机会
    - 资金费率 < -0.05%: 极度恐慌，做多信号 + 套利机会
    - 中性区间: 观望
    
    套利模式:
    - 永续做空 + 现货做多 (1:1对冲)
    - 每8小时收取资金费率
    """
    
    def __init__(self):
        # 阈值设置
        self.extreme_long_threshold = 0.001  # +0.1% 极度贪婪
        self.extreme_short_threshold = -0.0005  # -0.05% 极度恐慌
        self.moderate_long_threshold = 0.0005  # +0.05% 偏多
        self.moderate_short_threshold = -0.0003  # -0.03% 偏空
        
        # 历史数据缓存
        self.funding_history: Dict[str, list] = {}
        self.max_history = 90  # 保存30天数据 (每天3次)
    
    def update_funding_rate(self, symbol: str, rate: float, timestamp: Optional[datetime] = None):
        """
        更新资金费率历史
        """
        if symbol not in self.funding_history:
            self.funding_history[symbol] = []
        
        self.funding_history[symbol].append({
            'rate': rate,
            'timestamp': timestamp or datetime.now()
        })
        
        # 限制历史长度
        if len(self.funding_history[symbol]) > self.max_history:
            self.funding_history[symbol] = self.funding_history[symbol][-self.max_history:]
    
    def get_funding_stats(self, symbol: str) -> Dict:
        """
        获取资金费率统计
        """
        if symbol not in self.funding_history or len(self.funding_history[symbol]) < 3:
            return {
                'current': 0,
                'avg_7d': 0,
                'avg_30d': 0,
                'extreme_count_7d': 0,
                'trend': 'neutral'
            }
        
        history = self.funding_history[symbol]
        rates = [h['rate'] for h in history]
        
        current = rates[-1]
        avg_7d = np.mean(rates[-21:]) if len(rates) >= 21 else np.mean(rates)
        avg_30d = np.mean(rates) if len(rates) >= 90 else np.mean(rates)
        
        # 统计极端值次数
        extreme_count = sum(1 for r in rates[-21:] if abs(r) > 0.001)
        
        # 趋势判断
        if current > avg_7d * 1.5:
            trend = 'increasing'
        elif current < avg_7d * 0.5:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'current': current,
            'avg_7d': avg_7d,
            'avg_30d': avg_30d,
            'extreme_count_7d': extreme_count,
            'trend': trend
        }
    
    def evaluate_arbitrage(self, symbol: str, funding_rate: float) -> Optional[FundingRateSignal]:
        """
        评估套利机会
        
        策略:
        - 费率 > +0.1%: 永续做空 + 现货做多，收取费率
        - 费率 < -0.05%: 永续做多 + 现货做空，收取费率
        """
        annualized = funding_rate * 3 * 365  # 年化 (每天3次)
        
        # 极端多头费率 - 做空收费
        if funding_rate >= self.extreme_long_threshold:
            return FundingRateSignal(
                type='arbitrage',
                direction='short',  # 做空永续收费
                strength=min(funding_rate / 0.002, 1.0),  # 费率越高强度越大
                funding_rate=funding_rate,
                annualized_rate=annualized,
                description=f"资金费率套利: 做空永续+做多现货，年化收益 {annualized:.1f}%",
                expected_profit=funding_rate
            )
        
        # 极端空头费率 - 做多收费
        elif funding_rate <= self.extreme_short_threshold:
            return FundingRateSignal(
                type='arbitrage',
                direction='long',  # 做多永续收费
                strength=min(abs(funding_rate) / 0.001, 1.0),
                funding_rate=funding_rate,
                annualized_rate=annualized,
                description=f"资金费率套利: 做多永续+做空现货，年化收益 {annualized:.1f}%",
                expected_profit=abs(funding_rate)
            )
        
        return None
    
    def evaluate_trend(self, symbol: str, funding_rate: float, 
                       price_data: Optional[pd.DataFrame] = None) -> Optional[FundingRateSignal]:
        """
        评估趋势反转信号
        
        原理: 极端资金费率往往预示趋势反转
        """
        stats = self.get_funding_stats(symbol)
        
        # 极度贪婪 - 看跌信号
        if funding_rate >= self.extreme_long_threshold:
            # 如果RSI也超买，信号更强
            rsi_confirm = False
            if price_data is not None and len(price_data) > 14:
                from app.indicators import calculate_rsi
                df = calculate_rsi(price_data.copy())
                rsi_confirm = df['rsi'].iloc[-1] > 70
            
            strength = 0.7
            if rsi_confirm:
                strength = 0.85
            
            return FundingRateSignal(
                type='trend_reversal',
                direction='short',
                strength=strength,
                funding_rate=funding_rate,
                annualized_rate=funding_rate * 3 * 365,
                description=f"资金费率极度贪婪({funding_rate*100:.3f}%) + {'RSI超买确认' if rsi_confirm else '单独信号'} → 做空",
                expected_profit=0.05  # 预期5%收益
            )
        
        # 极度恐慌 - 看涨信号
        elif funding_rate <= self.extreme_short_threshold:
            # 如果RSI也超卖，信号更强
            rsi_confirm = False
            if price_data is not None and len(price_data) > 14:
                from app.indicators import calculate_rsi
                df = calculate_rsi(price_data.copy())
                rsi_confirm = df['rsi'].iloc[-1] < 30
            
            strength = 0.7
            if rsi_confirm:
                strength = 0.85
            
            return FundingRateSignal(
                type='trend_reversal',
                direction='long',
                strength=strength,
                funding_rate=funding_rate,
                annualized_rate=funding_rate * 3 * 365,
                description=f"资金费率极度恐慌({funding_rate*100:.3f}%) + {'RSI超卖确认' if rsi_confirm else '单独信号'} → 做多",
                expected_profit=0.05
            )
        
        return None
    
    def evaluate(self, symbol: str, funding_rate: float, 
                 price_data: Optional[pd.DataFrame] = None) -> Optional[FundingRateSignal]:
        """
        综合评估资金费率信号
        
        优先套利，其次趋势
        """
        # 更新历史
        self.update_funding_rate(symbol, funding_rate)
        
        # 检查套利机会 (优先级更高)
        arb_signal = self.evaluate_arbitrage(symbol, funding_rate)
        if arb_signal and arb_signal.strength > 0.8:
            return arb_signal
        
        # 检查趋势信号
        trend_signal = self.evaluate_trend(symbol, funding_rate, price_data)
        if trend_signal:
            return trend_signal
        
        return arb_signal  # 可能返回较弱的套利信号
    
    def get_funding_score(self, symbol: str, funding_rate: float) -> Tuple[int, str]:
        """
        获取资金费率评分
        
        返回: (分数 -100~100, 描述)
        """
        signal = self.evaluate(symbol, funding_rate)
        
        if signal is None:
            return 0, "资金费率中性"
        
        if signal.type == 'arbitrage':
            # 套利信号不直接产生方向评分，而是附加收益
            return 0, f"[套利机会] {signal.description}"
        
        # 趋势信号
        if signal.direction == 'long':
            return int(60 * signal.strength), signal.description
        else:
            return int(-60 * signal.strength), signal.description

# 全局实例
funding_strategy = FundingRateStrategy()
