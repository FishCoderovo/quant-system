"""
马丁格尔策略 (Martingale)
适用: 趋势回调，高风险高收益
原理: 亏损后加倍下注，快速回本
"""
import pandas as pd
from typing import Optional, Dict
from datetime import datetime
from app.strategies.base import Strategy, Signal
from app.config import settings

class MartingaleStrategy(Strategy):
    """
    马丁格尔策略 (带风险控制)
    
    原理:
    1. 首次建仓 1x 仓位
    2. 每跌 X% 加仓 2x 仓位
    3. 反弹 Y% 全部平仓
    4. 最大加仓次数限制，防止爆仓
    
    风险控制:
    - 最大加仓: 3 次 (1x → 2x → 4x)
    - 总仓位上限: 70%
    - 强制止损: -10%
    """
    
    def __init__(self):
        super().__init__("Martingale")
        self.max_additions = 3  # 最大加仓次数
        self.drop_threshold = 0.03  # 加仓跌幅 3%
        self.profit_target = 0.02  # 止盈目标 2%
        self.stop_loss = 0.10  # 强制止损 10%
        
        # 跟踪各币种状态
        self.positions: Dict[str, Dict] = {}
    
    def evaluate(self, symbol: str, df: pd.DataFrame,
                 has_position: bool = False) -> Optional[Signal]:
        """
        评估马丁格尔策略
        """
        if not self.enabled or len(df) < 20:
            return None
        
        latest = df.iloc[-1]
        current_price = latest['close']
        
        # 获取或初始化持仓状态
        if symbol not in self.positions:
            self.positions[symbol] = {
                'entry_price': None,
                'addition_count': 0,
                'total_amount': 0,
                'avg_price': 0,
                'last_addition_price': None,
                'started_at': None
            }
        
        pos = self.positions[symbol]
        
        # 情况1: 没有持仓 - 寻找首次建仓机会
        if pos['entry_price'] is None:
            # 条件: RSI 在 30-50 之间（超卖但不过度）
            rsi = latest.get('rsi', 50)
            if 30 < rsi < 50:
                pos['entry_price'] = current_price
                pos['addition_count'] = 0
                pos['total_amount'] = 1.0  # 1x 仓位
                pos['avg_price'] = current_price
                pos['last_addition_price'] = current_price
                pos['started_at'] = datetime.now()
                
                return Signal(
                    action='buy',
                    symbol=symbol,
                    strategy=self.name,
                    reason=f"马丁格尔首仓 1x @ {current_price:.2f} (RSI{rsi:.1f})",
                    score=55,
                    confidence=0.6
                )
            return None
        
        # 计算当前盈亏
        pnl_pct = (current_price - pos['avg_price']) / pos['avg_price']
        drop_from_last = (current_price - pos['last_addition_price']) / pos['last_addition_price']
        
        # 情况2: 有持仓，判断是否加仓
        if pos['addition_count'] < self.max_additions:
            # 跌幅达到阈值，触发加仓
            if drop_from_last <= -self.drop_threshold:
                next_addition = 2 ** (pos['addition_count'] + 1)  # 2x, 4x, 8x...
                
                # 风控: 总仓位检查
                total_position = pos['total_amount'] + next_addition
                if total_position <= 7.0:  # 最大 7x (约 70% 仓位)
                    pos['addition_count'] += 1
                    
                    # 更新均价
                    old_value = pos['total_amount'] * pos['avg_price']
                    new_value = next_addition * current_price
                    pos['total_amount'] = total_position
                    pos['avg_price'] = (old_value + new_value) / total_position
                    pos['last_addition_price'] = current_price
                    
                    return Signal(
                        action='buy',
                        symbol=symbol,
                        strategy=self.name,
                        reason=f"马丁格尔加仓 {pos['addition_count']}/{self.max_additions} 层 {next_addition}x @ {current_price:.2f}",
                        score=50 + pos['addition_count'] * 5,
                        confidence=0.55 - pos['addition_count'] * 0.05  # 越加信心越低
                    )
        
        # 情况3: 止盈平仓
        if pnl_pct >= self.profit_target:
            signal = Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"马丁格尔止盈 {pnl_pct*100:.2f}% (均价{pos['avg_price']:.2f})",
                score=70,
                confidence=0.75
            )
            # 重置状态
            self.reset_position(symbol)
            return signal
        
        # 情况4: 强制止损
        if pnl_pct <= -self.stop_loss:
            signal = Signal(
                action='sell',
                symbol=symbol,
                strategy=self.name,
                reason=f"马丁格尔止损 {pnl_pct*100:.2f}% (超过{self.stop_loss*100}%)",
                score=40,
                confidence=0.4
            )
            # 重置状态
            self.reset_position(symbol)
            return signal
        
        return None
    
    def reset_position(self, symbol: str):
        """重置持仓状态"""
        if symbol in self.positions:
            self.positions[symbol] = {
                'entry_price': None,
                'addition_count': 0,
                'total_amount': 0,
                'avg_price': 0,
                'last_addition_price': None,
                'started_at': None
            }
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """获取持仓信息"""
        return self.positions.get(symbol)

# 全局实例
martingale_strategy = MartingaleStrategy()
