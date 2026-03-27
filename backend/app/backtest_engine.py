"""
回测系统 (Backtest Engine)
策略历史数据回测与绩效分析
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
    strategy: str
    reason: str
    pnl: float = 0
    pnl_pct: float = 0

@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float  # 总收益率
    annualized_return: float  # 年化收益率
    sharpe_ratio: float  # 夏普比率
    max_drawdown: float  # 最大回撤
    win_rate: float  # 胜率
    profit_factor: float  # 盈亏比
    total_trades: int  # 总交易次数
    winning_trades: int  # 盈利次数
    losing_trades: int  # 亏损次数
    avg_profit: float  # 平均盈利
    avg_loss: float  # 平均亏损
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

class BacktestEngine:
    """
    回测引擎
    
    功能:
    1. 历史数据回测
    2. 策略绩效对比
    3. 参数优化
    4. 生成回测报告
    """
    
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, Dict] = {}  # 当前持仓
        self.trades: List[BacktestTrade] = []  # 交易记录
        self.equity_curve: List[float] = [initial_balance]  # 权益曲线
    
    def reset(self):
        """重置回测状态"""
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_balance]
    
    def run_backtest(self, 
                     data: pd.DataFrame,
                     strategy_func: Callable,
                     symbol: str = 'BTC/USDT') -> BacktestResult:
        """
        运行回测
        
        参数:
        - data: 历史数据 DataFrame
        - strategy_func: 策略函数，接收(df)返回Signal或None
        - symbol: 交易对
        """
        self.reset()
        
        # 计算指标
        data = calculate_all_indicators(data)
        
        # 逐K线回测
        for i in range(50, len(data)):  # 从第50根开始（确保有足够历史数据）
            current_data = data.iloc[:i+1]
            current_price = data['close'].iloc[i]
            current_time = data.index[i] if hasattr(data.index, 'iloc') else i
            
            # 获取策略信号
            signal = strategy_func(symbol, current_data)
            
            # 处理持仓检查 (止损/止盈)
            self._check_positions(current_price, current_time, symbol)
            
            # 执行信号
            if signal:
                if signal.action == 'buy':
                    self._execute_buy(signal, current_price, current_time)
                elif signal.action == 'sell':
                    self._execute_sell(signal, current_price, current_time)
            
            # 更新权益曲线
            total_value = self.balance + self._calculate_position_value(current_price)
            self.equity_curve.append(total_value)
        
        # 生成回测报告
        return self._generate_result()
    
    def _execute_buy(self, signal, price: float, timestamp):
        """执行买入"""
        # 计算仓位大小 (简化版：使用10%资金)
        position_value = self.balance * 0.1
        amount = position_value / price
        
        if amount <= 0:
            return
        
        # 记录持仓
        if signal.symbol not in self.positions:
            self.positions[signal.symbol] = {
                'amount': 0,
                'avg_price': 0,
                'total_cost': 0
            }
        
        pos = self.positions[signal.symbol]
        
        # 更新均价
        total_amount = pos['amount'] + amount
        total_cost = pos['total_cost'] + position_value
        pos['amount'] = total_amount
        pos['avg_price'] = total_cost / total_amount
        pos['total_cost'] = total_cost
        
        # 扣除资金
        self.balance -= position_value
        
        # 记录交易
        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            symbol=signal.symbol,
            action='buy',
            price=price,
            amount=amount,
            value=position_value,
            strategy=signal.strategy,
            reason=signal.reason
        ))
    
    def _execute_sell(self, signal, price: float, timestamp):
        """执行卖出"""
        if signal.symbol not in self.positions:
            return
        
        pos = self.positions[signal.symbol]
        if pos['amount'] <= 0:
            return
        
        # 计算盈亏
        sell_value = pos['amount'] * price
        pnl = sell_value - pos['total_cost']
        pnl_pct = pnl / pos['total_cost'] if pos['total_cost'] > 0 else 0
        
        # 增加资金
        self.balance += sell_value
        
        # 记录交易
        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            symbol=signal.symbol,
            action='sell',
            price=price,
            amount=pos['amount'],
            value=sell_value,
            strategy=signal.strategy,
            reason=signal.reason,
            pnl=pnl,
            pnl_pct=pnl_pct
        ))
        
        # 清空持仓
        del self.positions[signal.symbol]
    
    def _check_positions(self, current_price: float, timestamp, symbol: str):
        """检查持仓 (止损/止盈)"""
        # 简化版：这里可以实现移动止损逻辑
        pass
    
    def _calculate_position_value(self, current_price: float) -> float:
        """计算持仓价值"""
        total = 0
        for symbol, pos in self.positions.items():
            total += pos['amount'] * current_price
        return total
    
    def _generate_result(self) -> BacktestResult:
        """生成回测结果"""
        # 计算总收益
        final_value = self.equity_curve[-1]
        total_return = (final_value - self.initial_balance) / self.initial_balance
        
        # 计算胜率
        sell_trades = [t for t in self.trades if t.action == 'sell']
        winning_trades = len([t for t in sell_trades if t.pnl > 0])
        losing_trades = len([t for t in sell_trades if t.pnl <= 0])
        total_trades = len(sell_trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 计算盈亏比
        avg_profit = np.mean([t.pnl for t in sell_trades if t.pnl > 0]) if winning_trades > 0 else 0
        avg_loss = abs(np.mean([t.pnl for t in sell_trades if t.pnl <= 0])) if losing_trades > 0 else 1
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 计算最大回撤
        peak = self.initial_balance
        max_drawdown = 0
        for value in self.equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # 计算夏普比率 (简化版，假设无风险利率为0)
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # 年化收益 (假设数据是日线的)
        days = len(self.equity_curve)
        annualized_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        return BacktestResult(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            trades=self.trades,
            equity_curve=self.equity_curve
        )
    
    def compare_strategies(self, 
                          data: pd.DataFrame,
                          strategies: Dict[str, Callable]) -> Dict[str, BacktestResult]:
        """
        对比多个策略
        
        返回: {策略名: 回测结果}
        """
        results = {}
        for name, strategy_func in strategies.items():
            result = self.run_backtest(data, strategy_func)
            results[name] = result
        return results
    
    def optimize_params(self,
                       data: pd.DataFrame,
                       strategy_class,
                       param_grid: Dict[str, List]) -> Dict:
        """
        参数优化
        
        参数:
        - data: 历史数据
        - strategy_class: 策略类
        - param_grid: 参数网格，如 {'period': [10, 20, 30]}
        
        返回: 最优参数组合
        """
        best_sharpe = -np.inf
        best_params = {}
        
        # 这里简化实现，实际可以使用网格搜索或遗传算法
        # ...
        
        return best_params

# 全局实例
backtest_engine = BacktestEngine()
