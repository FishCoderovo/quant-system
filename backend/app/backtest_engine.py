"""
回测系统 v3.0 — 支持做多+做空
新增:
1. 做空持仓 (short position)
2. 合约手续费 (maker 0.02%, taker 0.05%)
3. 做空止损止盈 (方向相反)
4. 做空移动止损
5. 连续亏损保护
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
    timestamp: datetime
    symbol: str
    action: str  # 'buy', 'sell', 'short', 'cover'
    price: float
    amount: float
    value: float
    fee: float
    strategy: str
    reason: str
    direction: str = 'long'  # 'long' or 'short'
    pnl: float = 0
    pnl_pct: float = 0


@dataclass
class BacktestPosition:
    symbol: str
    amount: float
    entry_price: float
    total_cost: float      # 保证金 + 开仓手续费
    stop_loss: float
    take_profit: float
    atr: float
    highest_price: float   # long: 移动止损
    lowest_price: float    # short: 移动止损
    strategy: str
    direction: str = 'long'  # 'long' or 'short'


@dataclass
class BacktestResult:
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
    total_fees: float
    long_trades: int = 0
    short_trades: int = 0
    long_pnl: float = 0
    short_pnl: float = 0
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


class BacktestEngine:
    """
    回测引擎 v3.0 — 支持做多+做空

    做多: 现货模式 (买入持有)
    做空: 合约模式 (1x无杠杆，保证金=仓位价值)
    """

    # 现货手续费
    SPOT_MAKER_FEE = 0.0008   # 0.08%
    SPOT_TAKER_FEE = 0.0010   # 0.10%

    # 合约手续费 (做空用)
    CONTRACT_MAKER_FEE = 0.0002  # 0.02%
    CONTRACT_TAKER_FEE = 0.0005  # 0.05%

    # 止损倍数
    SL_ATR_MULT = 2.5

    # 盈亏比
    TREND_RR = 2.5
    RANGE_RR = 1.5
    TREND_STRATEGIES = {'TrendFollowing', 'Turtle'}

    # 连续亏损保护
    MAX_CONSECUTIVE_LOSSES = 3
    LOSS_COOLDOWN_BARS = 48  # 8天

    def __init__(self, initial_balance: float = 58.0, fee_type: str = 'maker'):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = [initial_balance]
        self.total_fees: float = 0
        self.spot_fee = self.SPOT_MAKER_FEE if fee_type == 'maker' else self.SPOT_TAKER_FEE
        self.contract_fee = self.CONTRACT_MAKER_FEE if fee_type == 'maker' else self.CONTRACT_TAKER_FEE
        self.consecutive_losses = 0
        self.cooldown_until_bar = -1

    def reset(self):
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_balance]
        self.total_fees = 0
        self.consecutive_losses = 0
        self.cooldown_until_bar = -1

    def run_backtest(self, data: pd.DataFrame, strategy_func: Callable,
                     symbol: str = 'BTC/USDT') -> BacktestResult:
        self.reset()
        data = calculate_all_indicators(data)

        for i in range(50, len(data)):
            current_data = data.iloc[:i + 1]
            row = data.iloc[i]
            price = row['close']
            high = row['high']
            low = row['low']
            atr = row.get('atr', price * 0.02)
            ts = data.index[i] if hasattr(data.index[0], 'isoformat') else i

            trades_before = len(self.trades)

            # 1. 检查持仓止损/止盈
            self._check_positions(symbol, high, low, price, atr, ts)

            # 2. 获取策略信号
            signal = strategy_func(symbol, current_data)

            # 3. 执行信号 (含冷却检查)
            if signal and symbol not in self.positions:
                if i >= self.cooldown_until_bar:
                    if signal.action == 'buy':
                        self._open_long(signal, price, atr, ts)
                    elif signal.action == 'short':
                        self._open_short(signal, price, atr, ts)
            elif signal and symbol in self.positions:
                pos = self.positions[symbol]
                if signal.action == 'sell' and pos.direction == 'long':
                    self._close_position(symbol, price, ts, signal.strategy, signal.reason)
                elif signal.action == 'cover' and pos.direction == 'short':
                    self._close_position(symbol, price, ts, signal.strategy, signal.reason)

            # 4. 更新连续亏损
            if len(self.trades) > trades_before:
                for t in self.trades[trades_before:]:
                    if t.action in ('sell', 'cover'):
                        if t.pnl < 0:
                            self.consecutive_losses += 1
                            if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
                                self.cooldown_until_bar = i + self.LOSS_COOLDOWN_BARS
                        elif t.pnl > 0:
                            self.consecutive_losses = 0

            # 5. 权益曲线
            total_value = self.balance + self._position_value(symbol, price)
            self.equity_curve.append(total_value)

        # 结束时平仓
        last_price = data['close'].iloc[-1]
        last_ts = data.index[-1] if hasattr(data.index[0], 'isoformat') else len(data) - 1
        if symbol in self.positions:
            self._close_position(symbol, last_price, last_ts, 'backtest', '回测结束平仓')
            self.equity_curve[-1] = self.balance

        return self._generate_result()

    # ------------------------------------------------------------------ #
    #  做多开仓
    # ------------------------------------------------------------------ #
    def _open_long(self, signal, price: float, atr: float, timestamp):
        stop_loss = price - self.SL_ATR_MULT * atr
        stop_dist_pct = (price - stop_loss) / price
        if stop_dist_pct <= 0 or stop_dist_pct > 0.20:
            return

        rr = self.TREND_RR if signal.strategy in self.TREND_STRATEGIES else self.RANGE_RR
        take_profit = price + (price - stop_loss) * rr

        risk_amount = self.balance * 0.02
        position_value = risk_amount / stop_dist_pct
        max_value = self.balance * settings.MAX_POSITION_PCT
        position_value = min(position_value, max_value)
        if position_value <= 0 or position_value > self.balance:
            position_value = min(position_value, self.balance * 0.95)
        if position_value <= 0:
            return

        amount = position_value / price
        fee = position_value * self.spot_fee
        total_cost = position_value + fee
        if total_cost > self.balance:
            position_value = self.balance / (1 + self.spot_fee) * 0.99
            amount = position_value / price
            fee = position_value * self.spot_fee
            total_cost = position_value + fee
        if amount <= 0:
            return

        self.balance -= total_cost
        self.total_fees += fee

        self.positions[signal.symbol] = BacktestPosition(
            symbol=signal.symbol, amount=amount, entry_price=price,
            total_cost=total_cost, stop_loss=stop_loss, take_profit=take_profit,
            atr=atr, highest_price=price, lowest_price=price,
            strategy=signal.strategy, direction='long'
        )
        self.trades.append(BacktestTrade(
            timestamp=timestamp, symbol=signal.symbol, action='buy',
            price=price, amount=amount, value=position_value, fee=fee,
            strategy=signal.strategy, reason=signal.reason, direction='long'
        ))

    # ------------------------------------------------------------------ #
    #  做空开仓
    # ------------------------------------------------------------------ #
    def _open_short(self, signal, price: float, atr: float, timestamp):
        stop_loss = price + self.SL_ATR_MULT * atr  # 止损在上方
        stop_dist_pct = (stop_loss - price) / price
        if stop_dist_pct <= 0 or stop_dist_pct > 0.20:
            return

        rr = self.TREND_RR if signal.strategy in self.TREND_STRATEGIES else self.RANGE_RR
        take_profit = price - (stop_loss - price) * rr  # 止盈在下方
        if take_profit <= 0:
            return

        # 仓位: 2%风险法则 (和做多一样)
        risk_amount = self.balance * 0.02
        position_value = risk_amount / stop_dist_pct
        max_value = self.balance * settings.MAX_POSITION_PCT
        position_value = min(position_value, max_value)
        if position_value <= 0 or position_value > self.balance:
            position_value = min(position_value, self.balance * 0.95)
        if position_value <= 0:
            return

        amount = position_value / price
        fee = position_value * self.contract_fee  # 合约手续费
        margin = position_value + fee  # 保证金 = 仓位价值 + 手续费

        if margin > self.balance:
            position_value = self.balance / (1 + self.contract_fee) * 0.99
            amount = position_value / price
            fee = position_value * self.contract_fee
            margin = position_value + fee
        if amount <= 0:
            return

        self.balance -= margin
        self.total_fees += fee

        self.positions[signal.symbol] = BacktestPosition(
            symbol=signal.symbol, amount=amount, entry_price=price,
            total_cost=margin, stop_loss=stop_loss, take_profit=take_profit,
            atr=atr, highest_price=price, lowest_price=price,
            strategy=signal.strategy, direction='short'
        )
        self.trades.append(BacktestTrade(
            timestamp=timestamp, symbol=signal.symbol, action='short',
            price=price, amount=amount, value=position_value, fee=fee,
            strategy=signal.strategy, reason=signal.reason, direction='short'
        ))

    # ------------------------------------------------------------------ #
    #  平仓 (做多/做空通用)
    # ------------------------------------------------------------------ #
    def _close_position(self, symbol: str, price: float, timestamp,
                        strategy: str, reason: str):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]

        if pos.direction == 'long':
            # 做多平仓: 卖出
            sell_value = pos.amount * price
            fee = sell_value * self.spot_fee
            pnl = (sell_value - fee) - pos.total_cost
            net_return = sell_value - fee
            action = 'sell'
        else:
            # 做空平仓: 买入归还
            close_value = pos.amount * price
            fee = close_value * self.contract_fee
            # 盈亏 = (入场价-平仓价) × amount - 开仓费 - 平仓费
            gross_pnl = pos.amount * (pos.entry_price - price)
            open_fee = pos.total_cost - (pos.amount * pos.entry_price)  # 开仓时的手续费
            pnl = gross_pnl - open_fee - fee
            # 归还保证金 + 盈亏
            net_return = pos.total_cost + pnl
            action = 'cover'

        pnl_pct = pnl / pos.total_cost if pos.total_cost > 0 else 0

        self.balance += max(0, net_return)  # 不能为负
        self.total_fees += fee

        self.trades.append(BacktestTrade(
            timestamp=timestamp, symbol=symbol, action=action,
            price=price, amount=pos.amount, value=pos.amount * price,
            fee=fee, strategy=strategy, reason=reason,
            direction=pos.direction, pnl=pnl, pnl_pct=pnl_pct
        ))
        del self.positions[symbol]

    # ------------------------------------------------------------------ #
    #  止损 / 止盈 / 移动止损
    # ------------------------------------------------------------------ #
    def _check_positions(self, symbol: str, high: float, low: float,
                         close: float, atr: float, timestamp):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]

        if pos.direction == 'long':
            # 做多: low触及止损, high触及止盈
            if low <= pos.stop_loss:
                self._close_position(symbol, pos.stop_loss, timestamp,
                                     pos.strategy, f'止损触发 SL={pos.stop_loss:.2f}')
                return
            if high >= pos.take_profit:
                self._close_position(symbol, pos.take_profit, timestamp,
                                     pos.strategy, f'止盈触发 TP={pos.take_profit:.2f}')
                return
            # 移动止损: 价格创新高 → 止损上移
            if high > pos.highest_price:
                pos.highest_price = high
                new_stop = high - self.SL_ATR_MULT * atr
                if new_stop > pos.stop_loss:
                    pos.stop_loss = new_stop

        elif pos.direction == 'short':
            # 做空: high触及止损(价格涨了), low触及止盈(价格跌了)
            if high >= pos.stop_loss:
                self._close_position(symbol, pos.stop_loss, timestamp,
                                     pos.strategy, f'空头止损 SL={pos.stop_loss:.2f}')
                return
            if low <= pos.take_profit:
                self._close_position(symbol, pos.take_profit, timestamp,
                                     pos.strategy, f'空头止盈 TP={pos.take_profit:.2f}')
                return
            # 移动止损: 价格创新低 → 止损下移
            if low < pos.lowest_price:
                pos.lowest_price = low
                new_stop = low + self.SL_ATR_MULT * atr
                if new_stop < pos.stop_loss:
                    pos.stop_loss = new_stop

    # ------------------------------------------------------------------ #
    #  辅助
    # ------------------------------------------------------------------ #
    def _position_value(self, symbol: str, price: float) -> float:
        if symbol not in self.positions:
            return 0
        pos = self.positions[symbol]
        if pos.direction == 'long':
            return pos.amount * price
        else:
            # 做空: 保证金 + 未实现盈亏
            unrealized_pnl = pos.amount * (pos.entry_price - price)
            return pos.total_cost + unrealized_pnl

    def _generate_result(self) -> BacktestResult:
        final_value = self.equity_curve[-1]
        total_return = (final_value - self.initial_balance) / self.initial_balance

        close_trades = [t for t in self.trades if t.action in ('sell', 'cover')]
        winning = [t for t in close_trades if t.pnl > 0]
        losing = [t for t in close_trades if t.pnl <= 0]
        total_trades = len(close_trades)
        win_rate = len(winning) / total_trades if total_trades > 0 else 0

        avg_profit = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0.001
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0

        # 做多/做空分别统计
        long_closes = [t for t in close_trades if t.direction == 'long']
        short_closes = [t for t in close_trades if t.direction == 'short']
        long_pnl = sum(t.pnl for t in long_closes)
        short_pnl = sum(t.pnl for t in short_closes)

        peak = self.initial_balance
        max_dd = 0
        for v in self.equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

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
            long_trades=len(long_closes),
            short_trades=len(short_closes),
            long_pnl=long_pnl,
            short_pnl=short_pnl,
            trades=self.trades,
            equity_curve=self.equity_curve
        )

    def compare_strategies(self, data: pd.DataFrame,
                           strategies: Dict[str, Callable]) -> Dict[str, BacktestResult]:
        results = {}
        for name, func in strategies.items():
            result = self.run_backtest(data, func)
            results[name] = result
        return results


backtest_engine = BacktestEngine(initial_balance=58.0, fee_type='maker')
