"""
策略引擎 v2.0 - 多策略并行，智能信号聚合
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from app.strategies.base import Strategy, Signal
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.oversold_bounce import OversoldBounceStrategy
from app.strategies.grid_trading import GridTradingStrategy
from app.strategies.martingale import MartingaleStrategy
from app.strategies.momentum_breakout import MomentumBreakoutStrategy
from app.indicators import calculate_all_indicators
from app.config import settings

class StrategyEngine:
    """
    策略引擎 v2.0
    
    新特性:
    1. 多策略并行运行
    2. 信号权重聚合
    3. 自适应策略选择
    4. 高级市场状态检测
    """
    
    def __init__(self):
        # 初始化所有策略
        self.strategies: Dict[str, Strategy] = {
            'trend_following': TrendFollowingStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'oversold_bounce': OversoldBounceStrategy(),
            'grid_trading': GridTradingStrategy(),
            'martingale': MartingaleStrategy(),
            'momentum_breakout': MomentumBreakoutStrategy()
        }
        
        # 策略权重 (用于信号聚合)
        self.strategy_weights = {
            'trend_following': 1.0,
            'mean_reversion': 1.0,
            'breakout': 1.0,
            'oversold_bounce': 0.8,
            'grid_trading': 1.2,  # 震荡市更优
            'martingale': 0.7,    # 风险较高，权重较低
            'momentum_breakout': 1.1  # 分钟级优势
        }
        
        # 当前活跃策略
        self.active_strategies: List[str] = []
        self.market_state: str = "unknown"
        
        # 模式: 'single' (单策略) 或 'parallel' (多策略并行)
        self.mode = 'parallel'
    
    def detect_market_state(self, df: pd.DataFrame) -> str:
        """
        增强版市场状态检测
        """
        if len(df) < 30:
            return "unknown"
        
        latest = df.iloc[-1]
        
        # 计算多周期涨幅
        price_5m_ago = df['close'].iloc[-5] if len(df) >= 5 else df['close'].iloc[0]
        price_20m_ago = df['close'].iloc[-20] if len(df) >= 20 else df['close'].iloc[0]
        
        current_price = df['close'].iloc[-1]
        change_5m = (current_price - price_5m_ago) / price_5m_ago * 100
        change_20m = (current_price - price_20m_ago) / price_20m_ago * 100
        
        # 波动率指标
        bb_width = latest.get('bb_width', 0.1)
        atr = latest.get('atr', current_price * 0.01)
        atr_pct = atr / current_price
        
        # 成交量
        volume_ratio = latest.get('volume_ratio', 1.0)
        
        # 市场状态判定
        if change_5m > 2 or change_20m > 5:
            return "strong_uptrend"
        elif change_5m > 0.5 or change_20m > 2:
            return "uptrend"
        elif change_5m < -2 or change_20m < -5:
            return "strong_downtrend"
        elif change_5m < -0.5 or change_20m < -2:
            return "downtrend"
        elif atr_pct > 0.02 and volume_ratio > 1.5:
            return "high_volatility"  # 高波动，适合突破策略
        elif bb_width < 0.03:
            return "low_volatility"  # 低波动，观望
        else:
            return "range_bound"  # 区间震荡
    
    def select_strategies(self, market_state: str) -> List[str]:
        """
        根据市场状态选择策略组合
        """
        strategy_map = {
            'strong_uptrend': ['trend_following', 'momentum_breakout'],
            'uptrend': ['trend_following', 'momentum_breakout'],
            'range_bound': ['mean_reversion', 'grid_trading'],
            'high_volatility': ['breakout', 'momentum_breakout'],
            'downtrend': ['oversold_bounce'],  # 仅超卖反弹
            'strong_downtrend': [],  # 观望
            'low_volatility': ['grid_trading'],  # 低波动做网格
        }
        
        return strategy_map.get(market_state, [])
    
    def aggregate_signals(self, signals: List[Tuple[Signal, float]]) -> Optional[Signal]:
        """
        聚合多策略信号
        
        逻辑:
        1. 计算加权分数
        2. 买入信号需满足: 加权分数 > 60 且 买入信号数 > 卖出信号数
        3. 卖出信号需满足: 加权分数 > 50 或 任一策略强烈卖出
        """
        if not signals:
            return None
        
        buy_signals = [s for s in signals if s[0].action == 'buy']
        sell_signals = [s for s in signals if s[0].action == 'sell']
        
        # 计算加权分数
        buy_score = sum(s[0].score * s[1] for s in buy_signals)
        sell_score = sum(s[0].score * s[1] for s in sell_signals)
        
        # 选择最强信号
        if buy_score > sell_score and buy_score > 60:
            # 选择最高分的买入信号
            best_signal = max(buy_signals, key=lambda x: x[0].score)[0]
            best_signal.score = min(int(buy_score / len(buy_signals)), 95)
            best_signal.reason = f"[聚合] {best_signal.reason} (共{len(buy_signals)}策略看涨)"
            return best_signal
        
        elif sell_score > 50:
            # 选择最高分的卖出信号
            best_signal = max(sell_signals, key=lambda x: x[0].score)[0]
            best_signal.score = min(int(sell_score / len(sell_signals)), 95)
            best_signal.reason = f"[聚合] {best_signal.reason} (共{len(sell_signals)}策略看跌)"
            return best_signal
        
        return None
    
    def evaluate_symbol_parallel(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """
        并行评估所有适用策略
        """
        if len(df) < 30:
            return None
        
        # 检测市场状态
        market_state = self.detect_market_state(df)
        self.market_state = market_state
        
        # 选择策略组合
        strategy_names = self.select_strategies(market_state)
        
        if not strategy_names:
            self.active_strategies = []
            return None
        
        # 收集所有信号
        signals = []
        for name in strategy_names:
            if name in self.strategies:
                strategy = self.strategies[name]
                if strategy.is_enabled():
                    signal = strategy.evaluate(symbol, df)
                    if signal:
                        weight = self.strategy_weights.get(name, 1.0)
                        signals.append((signal, weight))
        
        self.active_strategies = strategy_names
        
        # 聚合信号
        return self.aggregate_signals(signals)
    
    def evaluate_symbol_single(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """
        单策略模式 (兼容旧版)
        """
        if len(df) < 30:
            return None
        
        market_state = self.detect_market_state(df)
        self.market_state = market_state
        
        strategy_names = self.select_strategies(market_state)
        
        for name in strategy_names[:1]:  # 只取第一个
            if name in self.strategies:
                strategy = self.strategies[name]
                signal = strategy.evaluate(symbol, df)
                if signal:
                    self.active_strategies = [name]
                    return signal
        
        return None
    
    def evaluate_symbol(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """
        评估单个币种
        """
        if self.mode == 'parallel':
            return self.evaluate_symbol_parallel(symbol, df)
        else:
            return self.evaluate_symbol_single(symbol, df)
    
    def get_strategy_status(self) -> Dict:
        """获取策略状态"""
        return {
            'market_state': self.market_state,
            'mode': self.mode,
            'active_strategies': self.active_strategies,
            'strategies': {
                name: {
                    'enabled': strategy.is_enabled(),
                    'name': strategy.name,
                    'weight': self.strategy_weights.get(name, 1.0)
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
    
    def set_mode(self, mode: str):
        """设置运行模式"""
        if mode in ['single', 'parallel']:
            self.mode = mode

# 全局策略引擎实例
strategy_engine = StrategyEngine()
