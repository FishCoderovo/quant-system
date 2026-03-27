"""
策略引擎 - 根据市场状态自动选择和执行策略
"""
import pandas as pd
from typing import Dict, List, Optional
from app.strategies.base import Strategy, Signal
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.oversold_bounce import OversoldBounceStrategy
from app.indicators import calculate_all_indicators
from app.config import settings

class StrategyEngine:
    """策略引擎"""
    
    def __init__(self):
        # 初始化所有策略
        self.strategies: Dict[str, Strategy] = {
            'trend_following': TrendFollowingStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'oversold_bounce': OversoldBounceStrategy()
        }
        
        # 当前活跃策略
        self.active_strategy: Optional[str] = None
        
        # 市场状态
        self.market_state: str = "unknown"
    
    def detect_market_state(self, df: pd.DataFrame) -> str:
        """
        检测市场状态
        """
        if len(df) < 30:
            return "unknown"
        
        # 计算20日涨幅
        price_20_days_ago = df['close'].iloc[-20] if len(df) >= 20 else df['close'].iloc[0]
        current_price = df['close'].iloc[-1]
        price_change_20 = (current_price - price_20_days_ago) / price_20_days_ago * 100
        
        # 获取布林带宽度
        latest = df.iloc[-1]
        bb_width = latest.get('bb_width', 0.1)
        
        # 市场状态判定
        if price_change_20 > 15:
            return "strong_uptrend"  # 强劲上涨
        elif price_change_20 > 5:
            return "uptrend"  # 上涨趋势
        elif price_change_20 < -15:
            return "strong_downtrend"  # 强劲下跌
        elif price_change_20 < -5:
            return "downtrend"  # 下跌趋势
        elif bb_width < 0.05:
            return "low_volatility"  # 低波动
        else:
            return "range_bound"  # 区间震荡
    
    def select_strategy(self, market_state: str) -> Optional[Strategy]:
        """
        根据市场状态选择策略
        """
        strategy_map = {
            'strong_uptrend': 'trend_following',
            'uptrend': 'trend_following',
            'range_bound': 'mean_reversion',
            'high_volatility': 'breakout',
            'downtrend': None,  # 观望
            'strong_downtrend': None,  # 观望
            'low_volatility': None,  # 观望
        }
        
        strategy_name = strategy_map.get(market_state)
        if strategy_name and strategy_name in self.strategies:
            return self.strategies[strategy_name]
        return None
    
    def evaluate_symbol(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """
        评估单个币种
        """
        # 确保数据有足够的技术指标
        if len(df) < 30:
            return None
        
        # 检测市场状态
        market_state = self.detect_market_state(df)
        
        # 更新市场状态
        if market_state != self.market_state:
            self.market_state = market_state
        
        # 根据市场状态选择策略
        strategy = self.select_strategy(market_state)
        
        if strategy is None:
            return None
        
        # 执行策略评估
        signal = strategy.evaluate(symbol, df)
        
        if signal:
            self.active_strategy = strategy.name
        
        return signal
    
    def get_strategy_status(self) -> Dict:
        """获取策略状态"""
        return {
            'market_state': self.market_state,
            'active_strategy': self.active_strategy,
            'strategies': {
                name: {
                    'enabled': strategy.is_enabled(),
                    'name': strategy.name
                }
                for name, strategy in self.strategies.items()
            }
        }
    
    def toggle_strategy(self, strategy_name: str, enabled: bool):
        """开关策略"""
        if strategy_name in self.strategies:
            if enabled:
                self.strategies[strategy_name].enable()
            else:
                self.strategies[strategy_name].disable()

# 全局策略引擎实例
strategy_engine = StrategyEngine()
