"""
动量突破策略 (MomentumBreakout)
适用: 分钟级快速波动，追势交易
"""
import pandas as pd
import numpy as np
from typing import Optional
from app.strategies.base import Strategy, Signal
from app.config import settings

class MomentumBreakoutStrategy(Strategy):
    """
    动量突破策略
    
    原理:
    1. 监测短期动量 (5分钟/15分钟)
    2. 成交量突增 + 价格加速突破 = 追入信号
    3. 追踪止损，吃完整段行情
    
    特点:
    - 响应速度快，适合分钟级波动
    - 追涨杀跌，顺势而为
    - 高胜率但盈亏比相对较低
    """
    
    def __init__(self):
        super().__init__("MomentumBreakout")
        # 动量参数
        self.short_period = 5  # 5分钟短期动量
        self.medium_period = 15  # 15分钟中期动量
        self.volume_threshold = 2.0  # 成交量突增阈值 (2倍平均)
        self.momentum_threshold = 0.005  # 动量阈值 0.5%
        
        # 追踪止损
        self.trailing_stop_pct = 0.015  # 1.5% 回撤止损
        self.highest_price = {}  # 记录各币种最高价
    
    def calculate_momentum(self, df: pd.DataFrame, period: int) -> float:
        """
        计算动量
        """
        if len(df) < period:
            return 0
        
        current = df['close'].iloc[-1]
        past = df['close'].iloc[-period]
        return (current - past) / past
    
    def calculate_volume_surge(self, df: pd.DataFrame, period: int = 10) -> float:
        """
        计算成交量突增倍数
        """
        if len(df) < period + 1:
            return 1.0
        
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-period-1:-1].mean()
        
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume
    
    def detect_acceleration(self, df: pd.DataFrame) -> bool:
        """
        检测价格加速
        """
        if len(df) < 5:
            return False
        
        # 计算最近3根K线的平均涨幅
        recent_changes = []
        for i in range(-3, 0):
            change = (df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1]
            recent_changes.append(change)
        
        avg_change = np.mean(recent_changes)
        
        # 最近涨幅大于前面3根的平均涨幅 = 加速
        if len(df) >= 6:
            prev_changes = []
            for i in range(-6, -3):
                change = (df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1]
                prev_changes.append(change)
            prev_avg = np.mean(prev_changes)
            return avg_change > prev_avg * 1.5  # 当前加速50%以上
        
        return avg_change > 0.002  # 默认阈值 0.2%
    
    def evaluate(self, symbol: str, df: pd.DataFrame,
                 entry_price: Optional[float] = None) -> Optional[Signal]:
        """
        评估动量突破策略
        """
        if not self.enabled or len(df) < 20:
            return None
        
        latest = df.iloc[-1]
        current_price = latest['close']
        
        # 计算指标
        momentum_5m = self.calculate_momentum(df, self.short_period)
        momentum_15m = self.calculate_momentum(df, self.medium_period)
        volume_surge = self.calculate_volume_surge(df)
        is_accelerating = self.detect_acceleration(df)
        
        # 检查追踪止损 (如果有持仓)
        if symbol in self.highest_price:
            highest = self.highest_price[symbol]
            if current_price > highest:
                self.highest_price[symbol] = current_price
            else:
                drawdown = (highest - current_price) / highest
                if drawdown >= self.trailing_stop_pct:
                    # 触发追踪止损
                    del self.highest_price[symbol]
                    return Signal(
                        action='sell',
                        symbol=symbol,
                        strategy=self.name,
                        reason=f"动量追踪止损 回撤{drawdown*100:.2f}% (最高{highest:.2f})",
                        score=50,
                        confidence=0.6
                    )
        
        # 买入条件: 多因素共振
        # 1. 短期动量 > 阈值
        # 2. 中期动量 > 0 (趋势向上)
        # 3. 成交量突增
        # 4. 价格加速
        buy_conditions = [
            momentum_5m > self.momentum_threshold,
            momentum_15m > 0,
            volume_surge > self.volume_threshold,
            is_accelerating
        ]
        
        if all(buy_conditions):
            # 记录最高价用于追踪止损
            self.highest_price[symbol] = current_price
            
            return Signal(
                action='buy',
                symbol=symbol,
                strategy=self.name,
                reason=f"动量突破 5m动量{momentum_5m*100:.2f}% 成交量{volume_surge:.1f}x 加速{is_accelerating}",
                score=75 + min(volume_surge * 5, 20),  # 成交量越大分数越高
                confidence=0.75
            )
        
        # 卖出条件: 动量衰竭
        if momentum_5m < -self.momentum_threshold * 0.5 and symbol in self.highest_price:
            del self.highest_price[symbol]
            return Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"动量衰竭 5m动量{momentum_5m*100:.2f}%",
                score=55,
                confidence=0.55
            )
        
        return None
    
    def reset_tracking(self, symbol: str):
        """重置追踪止损"""
        if symbol in self.highest_price:
            del self.highest_price[symbol]

# 全局实例
momentum_strategy = MomentumBreakoutStrategy()
