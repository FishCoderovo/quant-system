"""
海龟交易法则 v3.0 — 支持做多+做空
核心规则:
1. 20日突破入场 (做多:突破高点, 做空:突破低点)
2. 10日突破出场 (做多:跌破低点, 做空:涨破高点)
3. 2N ATR止损
4. 金字塔加仓 (暂不用于做空)
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from app.strategies.base import Strategy, Signal
from app.config import settings

@dataclass
class TurtlePosition:
    entry_price: float
    entry_date: int
    unit_size: float
    stop_loss: float
    n_value: float
    add_count: int = 0
    direction: str = 'long'  # 'long' or 'short'

class TurtleStrategy(Strategy):
    def __init__(self):
        super().__init__("Turtle")
        self.entry_period = 20
        self.exit_period = 10
        self.atr_period = 20
        self.max_units = 4
        self.risk_per_trade = 0.01
        self.add_interval = 0.5
        self.positions: Dict[str, TurtlePosition] = {}
    
    def calculate_n(self, df: pd.DataFrame) -> float:
        if len(df) < self.atr_period + 1:
            return df['close'].iloc[-1] * 0.02
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(self.atr_period).mean().iloc[-1]
    
    def calculate_unit_size(self, n: float, account_value: float, 
                           current_price: float) -> float:
        risk_amount = account_value * self.risk_per_trade
        unit_value = risk_amount / n
        return unit_value / current_price
    
    def get_entry_signals(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        if len(df) < self.entry_period:
            return None, None
        highest_20 = df['high'].rolling(self.entry_period).max().iloc[-2]
        lowest_20 = df['low'].rolling(self.entry_period).min().iloc[-2]
        return highest_20, lowest_20
    
    def get_exit_signals(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        if len(df) < self.exit_period:
            return None, None
        lowest_10 = df['low'].rolling(self.exit_period).min().iloc[-2]
        highest_10 = df['high'].rolling(self.exit_period).max().iloc[-2]
        return lowest_10, highest_10
    
    def evaluate(self, symbol: str, df: pd.DataFrame,
                 account_value: float = 10000) -> Optional[Signal]:
        if not self.enabled or len(df) < self.entry_period + 5:
            return None
        
        latest = df.iloc[-1]
        current_price = latest['close']
        n = self.calculate_n(df)
        
        entry_long, entry_short = self.get_entry_signals(df)
        exit_long, exit_short = self.get_exit_signals(df)
        
        # ==================== 有持仓 ====================
        if symbol in self.positions:
            pos = self.positions[symbol]
            
            if pos.direction == 'long':
                # --- 做多持仓管理 ---
                if current_price <= pos.stop_loss:
                    del self.positions[symbol]
                    return Signal(
                        action='sell', symbol=symbol, strategy=self.name,
                        reason=f"海龟止损 2N={pos.n_value*2:.2f}",
                        score=50, confidence=0.6
                    )
                if exit_long and current_price < exit_long:
                    del self.positions[symbol]
                    return Signal(
                        action='sell', symbol=symbol, strategy=self.name,
                        reason=f"海龟10日突破出场 {exit_long:.2f}",
                        score=55, confidence=0.65
                    )
                # 加仓
                if pos.add_count < self.max_units - 1:
                    next_add = pos.entry_price + (pos.add_count + 1) * pos.n_value * self.add_interval
                    if current_price >= next_add:
                        pos.add_count += 1
                        pos.stop_loss = current_price - 2 * n
                        return Signal(
                            action='buy', symbol=symbol, strategy=self.name,
                            reason=f"海龟加仓 #{pos.add_count+1} @ {current_price:.2f}",
                            score=65, confidence=0.7
                        )
                # 移动止损
                new_stop = current_price - 2 * n
                if new_stop > pos.stop_loss:
                    pos.stop_loss = new_stop
            
            elif pos.direction == 'short':
                # --- 做空持仓管理 ---
                if current_price >= pos.stop_loss:
                    del self.positions[symbol]
                    return Signal(
                        action='cover', symbol=symbol, strategy=self.name,
                        reason=f"海龟空头止损 2N={pos.n_value*2:.2f}",
                        score=50, confidence=0.6
                    )
                if exit_short and current_price > exit_short:
                    del self.positions[symbol]
                    return Signal(
                        action='cover', symbol=symbol, strategy=self.name,
                        reason=f"海龟10日高点出场 {exit_short:.2f}",
                        score=55, confidence=0.65
                    )
                # 移动止损 (做空: 价格创新低时止损下移)
                new_stop = current_price + 2 * n
                if new_stop < pos.stop_loss:
                    pos.stop_loss = new_stop
        
        else:
            # ==================== 无持仓，检查入场 ====================
            
            # 20日突破做多
            if entry_long and current_price > entry_long:
                self.positions[symbol] = TurtlePosition(
                    entry_price=current_price,
                    entry_date=len(df) - 1,
                    unit_size=self.calculate_unit_size(n, account_value, current_price),
                    stop_loss=current_price - 2 * n,
                    n_value=n,
                    add_count=0,
                    direction='long'
                )
                return Signal(
                    action='buy', symbol=symbol, strategy=self.name,
                    reason=f"海龟20日突破做多 {entry_long:.2f} N={n:.2f}",
                    score=70, confidence=0.75
                )
            
            # 20日突破做空
            if entry_short and current_price < entry_short:
                self.positions[symbol] = TurtlePosition(
                    entry_price=current_price,
                    entry_date=len(df) - 1,
                    unit_size=self.calculate_unit_size(n, account_value, current_price),
                    stop_loss=current_price + 2 * n,  # 止损在上方
                    n_value=n,
                    add_count=0,
                    direction='short'
                )
                return Signal(
                    action='short', symbol=symbol, strategy=self.name,
                    reason=f"海龟20日突破做空 {entry_short:.2f} N={n:.2f}",
                    score=70, confidence=0.75
                )
        
        return None
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        return {
            'entry_price': pos.entry_price,
            'unit_size': pos.unit_size,
            'stop_loss': pos.stop_loss,
            'n_value': pos.n_value,
            'add_count': pos.add_count,
            'direction': pos.direction,
        }

turtle_strategy = TurtleStrategy()
