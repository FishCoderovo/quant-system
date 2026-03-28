"""
回测系统 v2.0 — 真实级别回测引擎
修复:
1. 止损止盈逻辑 (ATR动态止损 + 移动止损 + 止盈)
2. 手续费计算 (maker 0.08%, taker 0.10%)
3. 2%风险法则仓位计算
4. 正确的盈亏比 (配置化，默认2.5:1)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from app.indicators import calculate_all_indicators
from app.config import settings


@dataclass
class BacktestTrade:
    """回测交易记录"""
    timestamp: datetime
    symbol: str
    action: str  # 'buy', 'sell'
    price: float
    amount: float
    value: float
    fee: float  # 手续费
    strategy: str
    reason: str
    pnl: float = 0
    pnl_pct: float = 0


@dataclass
class BacktestPosition:
    """回测持仓"""
    symbol: str
    amount: float
    entry_price: float
    total_cost: float  # 含手续费的总成本
    stop_loss: float
    take_profit: float
    atr: float
    highest_price: float  # 用于移动止损
    strategy: str


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_profit: float
    avg_loss: float
    total_fees: float  # 总手续费
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


class BacktestEngine:
    """
    回测引擎 v2.0

    改进:
    1. ATR动态止损 + 移动止损 + 止盈
    2. 手续费: maker 0.08%, taker 0.10% (默认maker)
    3. 仓位: 2%风险法则 (账户2% / 止损距离)
    4. 最大仓位上限 70%
    5. 盈亏比检查 (≥ MIN_RISK_REWARD_RATIO)
    """

    # 手续费率
    MAKER_FEE = 0.0008  # 0.08%
    TAKER_FEE = 0.0010  # 0.10%

    # 止损倍数
    SL_ATR_MULT = 2.5   # ATR × 2.5 (从2.0放宽，减少被扫)

    # 分级盈亏比
    TREND_RR = 2.5       # 趋势策略
    RANGE_RR = 1.5       # 震荡策略
    TREND_STRATEGIES = {'TrendFollowing', 'Turtle'}

    def __init__(self, initial_balance: float = 58.0, fee_type: str = 'maker'):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = [initial_balance]
        self.total_fees: float = 0
        self.fee_rate = self.MAKER_FEE if fee_type == 'maker' else self.TAKER_FEE

    def reset(self):
        """重置回测状态"""
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_balance]
        self.total_fees = 0

    def run_backtest(self,
                     data: pd.DataFrame,
                     strategy_func: Callable,
                     symbol: str = 'BTC/USDT') -> BacktestResult:
        """运行回测"""
        self.reset()

        # 计算指标
        data = calculate_all_indicators(data)

        for i in range(50, len(data)):
            current_data = data.iloc[:i + 1]
            row = data.iloc[i]
            current_price = row['close']
            high_price = row['high']
            low_price = row['low']
            atr = row.get('atr', current_price * 0.02)
            current_time = data.index[i] if hasattr(data.index[0], 'isoformat') else i

            # ===== 1. 先检查持仓止损/止盈 (用high/low模拟盘中触发) =====
            self._check_positions(symbol, high_price, low_price, current_price, atr, current_time)

            # ===== 2. 获取策略信号 =====
            signal = strategy_func(symbol, current_data)

            # ===== 3. 执行信号 =====
            if signal:
                if signal.action == 'buy' and symbol not in self.positions:
                    self._execute_buy(signal, current_price, atr, current_time)
                elif signal.action == 'sell' and symbol in self.positions:
                    self._execute_sell(symbol, current_price, current_time,
                                       signal.strategy, signal.reason)

            # ===== 4. 更新权益曲线 =====
            total_value = self.balance + self._position_value(symbol, current_price)
            self.equity_curve.append(total_value)

        # 如果结束时还有持仓，按最后价格平仓
        last_price = data['close'].iloc[-1]
        last_time = data.index[-1] if hasattr(data.index[0], 'isoformat') else len(data) - 1
        if symbol in self.positions:
            self._execute_sell(symbol, last_price, last_time, 'backtest', '回测结束平仓')
            self.equity_curve[-1] = self.balance

        return self._generate_result()

    # ------------------------------------------------------------------ #
    #  买入
    # ------------------------------------------------------------------ #
    def _execute_buy(self, signal, price: float, atr: float, timestamp):
        """执行买入 — 2%风险法则 + ATR止损 + 盈亏比检查"""

        # 止损价 = 入场价 - SL_ATR_MULT × ATR
        stop_loss = price - self.SL_ATR_MULT * atr
        stop_distance_pct = (price - stop_loss) / price

        if stop_distance_pct <= 0 or stop_distance_pct > 0.20:
            return

        # 分级盈亏比: 趋势策略 2.5:1, 震荡策略 1.5:1
        rr = self.TREND_RR if signal.strategy in self.TREND_STRATEGIES else self.RANGE_RR
        risk = price - stop_loss
        take_profit = price + risk * rr

        reward = take_profit - price
        if risk <= 0 or reward / risk < rr:
            return

        # 仓位大小: (账户 × 2%) / 止损距离%
        risk_amount = self.balance * 0.02
        position_value = risk_amount / stop_distance_pct

        # 上限 70%
        max_value = self.balance * settings.MAX_POSITION_PCT
        position_value = min(position_value, max_value)

        # 确保有足够资金
        if position_value <= 0 or position_value > self.balance:
            position_value = min(position_value, self.balance * 0.95)
        if position_value <= 0:
            return

        amount = position_value / price

        # 手续费
        fee = position_value * self.fee_rate
        total_cost = position_value + fee

        if total_cost > self.balance:
            # 扣除手续费后重算
            position_value = self.balance / (1 + self.fee_rate) * 0.99
            amount = position_value / price
            fee = position_value * self.fee_rate
            total_cost = position_value + fee

        if amount <= 0:
            return

        # 扣资金
        self.balance -= total_cost
        self.total_fees += fee

        # 建仓
        self.positions[signal.symbol] = BacktestPosition(
            symbol=signal.symbol,
            amount=amount,
            entry_price=price,
            total_cost=total_cost,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
            highest_price=price,
            strategy=signal.strategy
        )

        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            symbol=signal.symbol,
            action='buy',
            price=price,
            amount=amount,
            value=position_value,
            fee=fee,
            strategy=signal.strategy,
            reason=signal.reason
        ))

    # ------------------------------------------------------------------ #
    #  卖出
    # ------------------------------------------------------------------ #
    def _execute_sell(self, symbol: str, price: float, timestamp,
                      strategy: str, reason: str):
        """执行卖出"""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        sell_value = pos.amount * price

        # 手续费
        fee = sell_value * self.fee_rate
        net_value = sell_value - fee

        # 盈亏 (扣除买入手续费)
        pnl = net_value - pos.total_cost
        pnl_pct = pnl / pos.total_cost if pos.total_cost > 0 else 0

        self.balance += net_value
        self.total_fees += fee

        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            action='sell',
            price=price,
            amount=pos.amount,
            value=sell_value,
            fee=fee,
            strategy=strategy,
            reason=reason,
            pnl=pnl,
            pnl_pct=pnl_pct
        ))

        del self.positions[symbol]

    # ------------------------------------------------------------------ #
    #  止损 / 止盈 / 移动止损
    # ------------------------------------------------------------------ #
    def _check_positions(self, symbol: str, high: float, low: float,
                         close: float, atr: float, timestamp):
        """检查持仓: ATR止损 + 移动止损 + 止盈"""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]

        # 1. 止损检查 (盘中最低价触及止损)
        if low <= pos.stop_loss:
            self._execute_sell(symbol, pos.stop_loss, timestamp,
                               pos.strategy, f'止损触发 SL={pos.stop_loss:.2f}')
            return

        # 2. 止盈检查 (盘中最高价触及止盈)
        if high >= pos.take_profit:
            self._execute_sell(symbol, pos.take_profit, timestamp,
                               pos.strategy, f'止盈触发 TP={pos.take_profit:.2f}')
            return

        # 3. 移动止损: 价格创新高时，止损跟随上移
        if high > pos.highest_price:
            pos.highest_price = high
            new_stop = high - self.SL_ATR_MULT * atr
            if new_stop > pos.stop_loss:
                pos.stop_loss = new_stop

    # ------------------------------------------------------------------ #
    #  辅助
    # ------------------------------------------------------------------ #
    def _position_value(self, symbol: str, price: float) -> float:
        """计算单个持仓的市值"""
        if symbol not in self.positions:
            return 0
        return self.positions[symbol].amount * price

    def _generate_result(self) -> BacktestResult:
        """生成回测结果"""
        final_value = self.equity_curve[-1]
        total_return = (final_value - self.initial_balance) / self.initial_balance

        sell_trades = [t for t in self.trades if t.action == 'sell']
        winning = [t for t in sell_trades if t.pnl > 0]
        losing = [t for t in sell_trades if t.pnl <= 0]
        total_trades = len(sell_trades)
        win_rate = len(winning) / total_trades if total_trades > 0 else 0

        avg_profit = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0.001
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0

        # 最大回撤
        peak = self.initial_balance
        max_dd = 0
        for v in self.equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        # 夏普比率
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)
                  if len(returns) > 1 and np.std(returns) > 0 else 0)

        days = max(len(self.equity_curve), 1)
        ann_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        return BacktestResult(
            total_return=total_return,
            annualized_return=ann_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_profit=float(avg_profit),
            avg_loss=float(avg_loss),
            total_fees=self.total_fees,
            trades=self.trades,
            equity_curve=self.equity_curve
        )

    # ------------------------------------------------------------------ #
    #  策略对比 & 参数优化
    # ------------------------------------------------------------------ #
    def compare_strategies(self,
                           data: pd.DataFrame,
                           strategies: Dict[str, Callable]) -> Dict[str, BacktestResult]:
        results = {}
        for name, func in strategies.items():
            result = self.run_backtest(data, func)
            results[name] = result
        return results

    def optimize_params(self, data: pd.DataFrame,
                        strategy_class, param_grid: Dict[str, list]) -> Dict:
        best_sharpe = -np.inf
        best_params = {}
        # TODO: 网格搜索
        return best_params


# 全局实例 — 初始余额 58 USDT (老板账户实际余额)
backtest_engine = BacktestEngine(initial_balance=58.0, fee_type='maker')
