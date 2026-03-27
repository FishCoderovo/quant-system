"""
海龟交易法则 (Turtle Trading System)
经典趋势跟踪策略

核心规则:
1. 20日突破入场
2. 10日突破出场
3. 2N ATR止损
4. 金字塔加仓 (每0.5N盈利加一次)
5. 总仓位不超过4个单位
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass
from app.strategies.base import Strategy, Signal
from app.config import settings

@dataclass
class TurtlePosition:
    """海龟持仓记录"""
    entry_price: float
    entry_date: int  # K线索引
    unit_size: float  # 单位大小
    stop_loss: float  # 止损价
    n_value: float  # ATR(N)值
    add_count: int = 0  # 加仓次数

class TurtleStrategy(Strategy):
    """
    海龟交易法则策略
    
    参数:
    - entry_period: 20 (20日突破入场)
    - exit_period: 10 (10日突破出场)
    - atr_period: 20 (20日ATR计算N值)
    - max_units: 4 (最大4个单位)
    - risk_per_trade: 0.01 (每笔风险1%账户)
    """
    
    def __init__(self):
        super().__init__("Turtle")
        self.entry_period = 20  # 20日突破
        self.exit_period = 10  # 10日突破出场
        self.atr_period = 20  # 20日ATR
        self.max_units = 4  # 最多4个单位
        self.risk_per_trade = 0.01  # 每笔风险1%
        self.add_interval = 0.5  # 每0.5N盈利加仓
        
        # 持仓跟踪
        self.positions: Dict[str, TurtlePosition] = {}
    
    def calculate_n(self, df: pd.DataFrame) -> float:
        """
        计算N值 (20日ATR)
        """
        if len(df) < self.atr_period + 1:
            return df['close'].iloc[-1] * 0.02  # 默认2%
        
        # 计算TR
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 20日平均
        n = tr.rolling(self.atr_period).mean().iloc[-1]
        
        return n
    
    def calculate_unit_size(self, n: float, account_value: float, 
                           current_price: float) -> float:
        """
        计算单位大小
        
        公式: 单位 = (账户 × 1%) / N
        """
        risk_amount = account_value * self.risk_per_trade
        unit_value = risk_amount / n
        unit_size = unit_value / current_price
        
        return unit_size
    
    def get_entry_signals(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """
        获取入场信号
        
        返回: (做多入场价, 做空入场价)
        """
        if len(df) < self.entry_period:
            return None, None
        
        # 20日最高/最低
        highest_20 = df['high'].rolling(self.entry_period).max().iloc[-2]  # 前一日的高点
        lowest_20 = df['low'].rolling(self.entry_period).min().iloc[-2]
        
        return highest_20, lowest_20
    
    def get_exit_signals(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """
        获取出场信号
        
        返回: (多头出场价, 空头出场价)
        """
        if len(df) < self.exit_period:
            return None, None
        
        # 10日最低/最高
        lowest_10 = df['low'].rolling(self.exit_period).min().iloc[-2]
        highest_10 = df['high'].rolling(self.exit_period).max().iloc[-2]
        
        return lowest_10, highest_10
    
    def evaluate(self, symbol: str, df: pd.DataFrame,
                 account_value: float = 10000) -> Optional[Signal]:
        """
        评估海龟信号
        """
        if not self.enabled or len(df) < self.entry_period + 5:
            return None
        
        latest = df.iloc[-1]
        current_price = latest['close']
        
        # 计算N值
        n = self.calculate_n(df)
        
        # 获取突破价位
        entry_long, entry_short = self.get_entry_signals(df)
        exit_long, exit_short = self.get_exit_signals(df)
        
        # 检查现有持仓
        if symbol in self.positions:
            pos = self.positions[symbol]
            
            # 检查止损
            if current_price <= pos.stop_loss:
                del self.positions[symbol]
                return Signal(
                    action='sell',
                    symbol=symbol,
                    strategy=self.name,
                    reason=f"海龟止损 2N={pos.n_value*2:.2f}",
                    score=50,
                    confidence=0.6
                )
            
            # 检查10日突破出场
            if exit_long and current_price < exit_long:
                del self.positions[symbol]
                return Signal(
                    action='sell',
                    symbol=symbol,
                    strategy=self.name,
                    reason=f"海龟10日突破出场 {exit_long:.2f}",
                    score=55,
                    confidence=0.65
                )
            
            # 检查加仓条件
            if pos.add_count < self.max_units - 1:
                # 每盈利0.5N加仓一次
                next_add_price = pos.entry_price + (pos.add_count + 1) * pos.n_value * self.add_interval
                
                if current_price >= next_add_price:
                    # 加仓
                    pos.add_count += 1
                    # 更新止损
                    pos.stop_loss = current_price - 2 * n
                    
                    unit_size = self.calculate_unit_size(n, account_value, current_price)
                    
                    return Signal(
                        action='buy',
                        symbol=symbol,
                        strategy=self.name,
                        reason=f"海龟金字塔加仓 #{pos.add_count+1} @ {current_price:.2f} (N={n:.2f})",
                        score=65,
                        confidence=0.7
                    )
            
            # 更新移动止损
            new_stop = current_price - 2 * n
            if new_stop > pos.stop_loss:
                pos.stop_loss = new_stop
        
        else:
            # 无持仓，检查入场信号
            
            # 20日突破做多
            if entry_long and current_price > entry_long:
                unit_size = self.calculate_unit_size(n, account_value, current_price)
                
                self.positions[symbol] = TurtlePosition(
                    entry_price=current_price,
                    entry_date=len(df) - 1,
                    unit_size=unit_size,
                    stop_loss=current_price - 2 * n,
                    n_value=n,
                    add_count=0
                )
                
                return Signal(
                    action='buy',
                    symbol=symbol,
                    strategy=self.name,
                    reason=f"海龟20日突破入场 {entry_long:.2f} N={n:.2f} 止损={current_price - 2*n:.2f}",
                    score=70,
                    confidence=0.75
                )
        
        return None
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """获取持仓信息"""
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        return {
            'entry_price': pos.entry_price,
            'unit_size': pos.unit_size,
            'stop_loss': pos.stop_loss,
            'n_value': pos.n_value,
            'add_count': pos.add_count,
            'total_risk': pos.n_value * 2 * (pos.add_count + 1)
        }

# 全局实例
turtle_strategy = TurtleStrategy()
