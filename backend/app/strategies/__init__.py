"""
策略基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
import pandas as pd

class Signal:
    """交易信号"""
    def __init__(self, 
                 action: str,  # 'buy', 'sell'
                 symbol: str,
                 strategy: str,
                 reason: str,
                 score: int = 0,
                 confidence: float = 0.0):
        self.action = action
        self.symbol = symbol
        self.strategy = strategy
        self.reason = reason
        self.score = score  # 共振评分
        self.confidence = confidence
    
    def to_dict(self) -> Dict:
        return {
            'action': self.action,
            'symbol': self.symbol,
            'strategy': self.strategy,
            'reason': self.reason,
            'score': self.score,
            'confidence': self.confidence
        }

class Strategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
    
    @abstractmethod
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """
        评估策略，返回交易信号或 None
        """
        pass
    
    def is_enabled(self) -> bool:
        return self.enabled
    
    def enable(self):
        self.enabled = True
    
    def disable(self):
        self.enabled = False
