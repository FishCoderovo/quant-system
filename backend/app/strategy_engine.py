"""
策略引擎 v3.1 - 多时间框架版
集成:
- 8种基础策略
- 量价背离检测
- Wyckoff周期分析
- 资金费率策略
- 海龟交易法则
- 多时间框架共振 (NEW)
- 多维度信号聚合
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from app.strategies.base import Strategy, Signal
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.grid_trading import GridTradingStrategy
from app.strategies.turtle import TurtleStrategy
from app.divergence_detector import divergence_detector, DivergenceSignal
from app.wyckoff_analyzer import wyckoff_analyzer, WyckoffPhase
from app.funding_strategy import funding_strategy, FundingRateSignal
from app.multi_timeframe import mtf_analyzer, TrendDirection
from app.indicators import calculate_all_indicators
from app.config import settings

class StrategyEngine:
    """
    策略引擎 v3.2 - 精简版
    
    改进:
    1. 砍掉无效策略，只保留4个核心策略
    2. 提高盈亏比到2.5:1
    3. 降低交易频率，提高信号质量
    4. 保留多时间框架共振过滤
    """
    
    def __init__(self):
        # 终极精简：只保留2个趋势策略
        # 砍掉 MeanReversion (信号多质量低) 和 GridTrading (单边市亏钱)
        self.strategies: Dict[str, Strategy] = {
            'trend_following': TrendFollowingStrategy(),
            'turtle': TurtleStrategy()
        }
        
        self.strategy_weights = {
            'trend_following': 1.2,
            'turtle': 1.3
        }
        
        # 状态
        self.active_strategies: List[str] = []
        self.active_strategy: Optional[str] = None  # 兼容旧API
        self.market_state: str = "unknown"
        self.mode = 'parallel'
        
        # 分析器
        self.divergence_detector = divergence_detector
        self.wyckoff_analyzer = wyckoff_analyzer
        self.funding_strategy = funding_strategy
        self.mtf_analyzer = mtf_analyzer
        
        # 分析结果缓存
        self.last_analysis = {}
        self.last_resonance = {}
    
    def analyze_market(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        综合分析市场
        
        返回多维度分析结果
        """
        analysis = {
            'symbol': symbol,
            'timestamp': pd.Timestamp.now(),
            'divergence': None,
            'wyckoff': None,
            'funding': None,
            'composite_score': 0,
            'signals': []
        }
        
        # 1. 量价背离分析
        if len(df) >= 20:
            div_signal = self.divergence_detector.detect_divergence(df)
            if div_signal:
                analysis['divergence'] = {
                    'type': div_signal.type,
                    'strength': div_signal.strength,
                    'description': div_signal.description
                }
                # 背离贡献分数
                if div_signal.type == 'bottom':
                    analysis['composite_score'] += div_signal.strength * 30
                    analysis['signals'].append('底背离看涨')
                else:
                    analysis['composite_score'] -= div_signal.strength * 30
                    analysis['signals'].append('顶背离看跌')
        
        # 2. Wyckoff周期分析
        if len(df) >= 50:
            wyckoff = self.wyckoff_analyzer.analyze_phase(df)
            analysis['wyckoff'] = {
                'phase': wyckoff.phase.value,
                'confidence': wyckoff.confidence,
                'event': wyckoff.event.value if wyckoff.event else None,
                'recommendation': wyckoff.recommendation,
                'support': wyckoff.support_level,
                'resistance': wyckoff.resistance_level
            }
            # Wyckoff贡献分数
            phase_scores = {
                WyckoffPhase.ACCUMULATION: 20,
                WyckoffPhase.MARKUP: 30,
                WyckoffPhase.DISTRIBUTION: -20,
                WyckoffPhase.MARKDOWN: -30,
                WyckoffPhase.UNKNOWN: 0
            }
            analysis['composite_score'] += phase_scores.get(wyckoff.phase, 0) * wyckoff.confidence
            analysis['signals'].append(f"Wyckoff: {wyckoff.phase.value}")
        
        # 3. 基础策略分析
        market_state = self.detect_market_state(df)
        analysis['market_state'] = market_state
        
        self.last_analysis[symbol] = analysis
        return analysis
    
    def detect_market_state(self, df: pd.DataFrame) -> str:
        """
        检测市场状态 — v3: 超强趋势过滤
        
        逻辑 (按优先级):
        1. MA排列: 空头→下跌, 多头→上涨
        2. 价格+MA20关系: 价格<MA20 且 MA20下降 → 下跌
        3. 涨跌幅+波动率: 兜底判断
        """
        if len(df) < 30:
            return "unknown"
        
        latest = df.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        ma5 = latest.get('ma5', 0)
        ma10 = latest.get('ma10', 0)
        ma20 = latest.get('ma20', 0)
        
        price_5 = df['close'].iloc[-5] if len(df) >= 5 else df['close'].iloc[0]
        price_20 = df['close'].iloc[-20] if len(df) >= 20 else df['close'].iloc[0]
        chg5 = (current_price - price_5) / price_5 * 100
        chg20 = (current_price - price_20) / price_20 * 100
        
        bb_width = latest.get('bb_width', 0.1)
        atr = latest.get('atr', current_price * 0.01)
        atr_pct = atr / current_price
        volume_ratio = latest.get('volume_ratio', 1.0)
        
        # ===== 1. MA排列 (最高优先级) =====
        if ma5 > 0 and ma10 > 0 and ma20 > 0:
            if ma5 < ma10 < ma20:
                return "strong_downtrend" if chg20 < -5 else "downtrend"
            if ma5 > ma10 > ma20:
                return "strong_uptrend" if chg20 > 5 else "uptrend"
        
        # ===== 2. 价格<MA20 + MA20下降 → 下跌 =====
        if ma20 > 0 and current_price < ma20:
            # 检查MA20是否在下降
            if len(df) >= 25:
                ma20_prev = df['close'].iloc[-25:-5].mean()  # 5根K线前的MA20近似值
                if ma20 < ma20_prev:
                    return "downtrend"
        
        # ===== 3. 价格>MA20 + MA20上升 → 才可能是上涨 =====
        if ma20 > 0 and current_price > ma20:
            if len(df) >= 25:
                ma20_prev = df['close'].iloc[-25:-5].mean()
                if ma20 > ma20_prev and chg5 > 0.5:
                    return "uptrend"
        
        # ===== 4. 涨跌幅兜底 =====
        if chg5 > 2 or chg20 > 5:
            return "strong_uptrend"
        elif chg5 < -2 or chg20 < -5:
            return "strong_downtrend"
        elif chg5 < -0.5 or chg20 < -2:
            return "downtrend"
        elif atr_pct > 0.02 and volume_ratio > 1.5:
            return "high_volatility"
        elif bb_width < 0.03:
            return "low_volatility"
        else:
            return "range_bound"
    
    def select_strategies(self, market_state: str) -> List[str]:
        """选择策略 — v3: 双向交易，上涨做多/下跌做空"""
        strategy_map = {
            'strong_uptrend': ['trend_following', 'turtle'],
            'uptrend': ['trend_following', 'turtle'],
            'range_bound': [],              # 震荡不交易
            'high_volatility': ['turtle'],
            'downtrend': ['trend_following', 'turtle'],      # 做空！
            'strong_downtrend': ['trend_following', 'turtle'], # 做空！
            'low_volatility': [],
        }
        return strategy_map.get(market_state, [])
    
    def evaluate_symbol(self, symbol: str, df: pd.DataFrame,
                       funding_rate: Optional[float] = None) -> Optional[Signal]:
        """
        综合评估 - 终极版
        """
        if len(df) < 30:
            return None
        
        # 1. 市场综合分析
        analysis = self.analyze_market(symbol, df)
        
        # 2. 资金费率分析 (如果提供)
        if funding_rate is not None:
            funding_signal = self.funding_strategy.evaluate(symbol, funding_rate, df)
            if funding_signal and funding_signal.strength > 0.7:
                # LONG_ONLY: 跳过做空方向的资金费率信号
                if settings.LONG_ONLY and funding_signal.direction != 'long':
                    print(f"[{symbol}] LONG_ONLY: 跳过做空资金费率信号")
                else:
                    # 资金费率信号很强，直接采用
                    return Signal(
                        action='buy' if funding_signal.direction == 'long' else 'sell',
                        symbol=symbol,
                        strategy=f"FundingRate-{funding_signal.type}",
                        reason=funding_signal.description,
                        score=int(funding_signal.strength * 80),
                        confidence=funding_signal.strength
                    )
        
        # 3. 基础策略评估
        signals = []
        market_state = analysis['market_state']
        strategy_names = self.select_strategies(market_state)
        
        for name in strategy_names:
            if name in self.strategies:
                strategy = self.strategies[name]
                if strategy.is_enabled():
                    signal = strategy.evaluate(symbol, df)
                    if signal:
                        weight = self.strategy_weights.get(name, 1.0)
                        signals.append((signal, weight))
        
        self.active_strategies = strategy_names
        self.market_state = market_state
        
        # 3.5 多时间框架共振分析 (NEW)
        # 只有当基础策略有信号时才检查共振
        if signals:
            try:
                resonance = self.mtf_analyzer.analyze(symbol)
                if resonance:
                    self.last_resonance[symbol] = resonance
                    
                    # 共振检查：如果共振不足，大幅降低信号分数或取消交易
                    if not resonance.tradeable:
                        print(f"[{symbol}] 共振不足({resonance.score:.0f}分，需{self.mtf_analyzer.MIN_RESONANCE_SCORE})，信号降级")
                        # 大幅降低信号权重
                        for i, (signal, weight) in enumerate(signals):
                            signals[i] = (signal, weight * 0.3)  # 信号权重降至30%
                    else:
                        print(f"[{symbol}] 共振确认({resonance.score:.0f}分，{resonance.description})")
                        # 共振确认，信号增强
                        for i, (signal, weight) in enumerate(signals):
                            if signal.action == 'buy' and resonance.direction.value in ['up', 'strong_up']:
                                signals[i] = (signal, weight * 1.3)
                            elif signal.action == 'sell' and resonance.direction.value in ['down', 'strong_down']:
                                signals[i] = (signal, weight * 1.3)
            except Exception as e:
                print(f"[{symbol}] 多时间框架分析失败: {e}")
        
        # 4. 信号聚合
        aggregated = self.aggregate_signals(signals)
        
        # 5. 结合背离和Wyckoff分析
        if aggregated:
            # 增强信号
            score_boost = analysis['composite_score'] * 0.3
            aggregated.score = min(95, max(10, int(aggregated.score + score_boost)))
            
            # 添加分析信息
            if analysis['signals']:
                aggregated.reason = f"{aggregated.reason} | {'; '.join(analysis['signals'][:2])}"
            
            # 更新活跃策略字符串（兼容旧API）
            self.active_strategy = aggregated.strategy
        
        # LONG_ONLY: 过滤做空信号
        if settings.LONG_ONLY and aggregated and aggregated.action in ('short', 'cover'):
            print(f"[{aggregated.symbol}] LONG_ONLY: 过滤做空信号 {aggregated.action}")
            return None
        
        return aggregated
    
    def aggregate_signals(self, signals: List[Tuple[Signal, float]]) -> Optional[Signal]:
        """聚合信号"""
        if not signals:
            return None
        
        buy_signals = [s for s in signals if s[0].action == 'buy']
        sell_signals = [s for s in signals if s[0].action == 'sell']
        
        buy_score = sum(s[0].score * s[1] for s in buy_signals)
        sell_score = sum(s[0].score * s[1] for s in sell_signals)
        
        if buy_score > sell_score and buy_score > 50:
            best = max(buy_signals, key=lambda x: x[0].score)[0]
            best.score = min(95, int(buy_score / len(buy_signals)))
            return best
        elif sell_score > 40:
            best = max(sell_signals, key=lambda x: x[0].score)[0]
            best.score = min(95, int(sell_score / len(sell_signals)))
            return best
        
        return None
    
    def get_strategy_status(self) -> Dict:
        """获取策略状态"""
        # 转换numpy类型为Python原生类型
        def to_native(val):
            import numpy as np
            if isinstance(val, np.bool_):
                return bool(val)
            if isinstance(val, (np.integer, np.int64)):
                return int(val)
            if isinstance(val, (np.floating, np.float64)):
                return float(val)
            return val
        
        return {
            'market_state': self.market_state,
            'mode': self.mode,
            'active_strategies': [to_native(s) for s in self.active_strategies],
            'strategies': {
                name: {
                    'enabled': to_native(strategy.is_enabled()),
                    'name': strategy.name,
                    'weight': to_native(self.strategy_weights.get(name, 1.0))
                }
                for name, strategy in self.strategies.items()
            },
            'analyzers': {
                'divergence': 'enabled',
                'wyckoff': 'enabled',
                'funding': 'enabled',
                'multi_timeframe': 'enabled'
            },
            'resonance': {
                symbol: {
                    'score': to_native(r.score),
                    'direction': str(r.direction.value) if hasattr(r.direction, 'value') else str(r.direction),
                    'aligned': f"{to_native(r.aligned_count)}/{to_native(r.total_count)}",
                    'tradeable': to_native(r.tradeable),
                    'description': str(r.description)
                }
                for symbol, r in self.last_resonance.items()
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
        """设置模式"""
        if mode in ['single', 'parallel']:
            self.mode = mode

# 全局实例
strategy_engine = StrategyEngine()
