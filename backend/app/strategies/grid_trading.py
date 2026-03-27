"""
网格交易策略 (GridTrading)
适用: 震荡市场，自动高抛低吸
比 MeanReversion 更系统化、更激进
"""
import pandas as pd
from typing import Optional, List, Dict
from app.strategies.base import Strategy, Signal
from app.config import settings

class GridTradingStrategy(Strategy):
    """
    网格交易策略
    
    原理:
    1. 根据当前价格设定上下区间
    2. 在区间内均匀布设网格
    3. 价格触及下网格买入，触及上网格卖出
    4. 循环套利，震荡市盈利神器
    """
    
    def __init__(self):
        super().__init__("GridTrading")
        # 网格配置
        self.grid_count = 5  # 网格数量
        self.grid_spacing = 0.02  # 网格间距 2%
        self.grids: Dict[str, List[Dict]] = {}  # 每个币种的网格状态
    
    def calculate_grids(self, center_price: float) -> List[float]:
        """
        计算网格价格
        """
        grids = []
        half_count = self.grid_count // 2
        
        for i in range(-half_count, half_count + 1):
            grid_price = center_price * (1 + i * self.grid_spacing)
            grids.append(grid_price)
        
        return sorted(grids)
    
    def get_grid_position(self, price: float, grids: List[float]) -> int:
        """
        获取当前价格所在网格位置
        """
        for i, grid_price in enumerate(grids):
            if price <= grid_price:
                return i
        return len(grids)
    
    def evaluate(self, symbol: str, df: pd.DataFrame, 
                 current_position: Optional[Dict] = None) -> Optional[Signal]:
        """
        评估网格策略
        """
        if not self.enabled or len(df) < 30:
            return None
        
        latest = df.iloc[-1]
        current_price = latest['close']
        
        # 初始化网格
        if symbol not in self.grids:
            # 以当前价格为中心建立网格
            grids = self.calculate_grids(current_price)
            self.grids[symbol] = {
                'center_price': current_price,
                'grids': grids,
                'last_grid_idx': self.get_grid_position(current_price, grids),
                'buy_count': 0,  # 当前持筹层数
                'buy_prices': []  # 每层买入价格
            }
            return None
        
        grid_state = self.grids[symbol]
        grids = grid_state['grids']
        current_grid_idx = self.get_grid_position(current_price, grids)
        last_grid_idx = grid_state['last_grid_idx']
        
        signal = None
        
        # 价格向下突破网格 - 买入信号
        if current_grid_idx < last_grid_idx:
            # 计算应该买入的层数
            grids_moved = last_grid_idx - current_grid_idx
            
            for i in range(grids_moved):
                buy_grid_idx = last_grid_idx - i - 1
                if buy_grid_idx >= 0 and buy_grid_idx < len(grids):
                    buy_price = grids[buy_grid_idx]
                    
                    # 风控检查：最多持有 grid_count 层
                    if grid_state['buy_count'] < self.grid_count:
                        signal = Signal(
                            action='buy',
                            symbol=symbol,
                            strategy=self.name,
                            reason=f"网格买入 第{grid_state['buy_count']+1}层 @ {buy_price:.2f}",
                            score=60 + grid_state['buy_count'] * 5,  # 分数随层数增加
                            confidence=0.7
                        )
                        grid_state['buy_count'] += 1
                        grid_state['buy_prices'].append(buy_price)
                        break
        
        # 价格向上突破网格 - 卖出信号
        elif current_grid_idx > last_grid_idx and grid_state['buy_count'] > 0:
            # 计算应该卖出的层数
            grids_moved = current_grid_idx - last_grid_idx
            
            for i in range(min(grids_moved, grid_state['buy_count'])):
                # 卖出成本最低的那层
                if grid_state['buy_prices']:
                    sell_price = grid_state['buy_prices'].pop(0)  # FIFO
                    grid_state['buy_count'] -= 1
                    
                    signal = Signal(
                        action='sell',
                        symbol=symbol,
                        strategy=self.name,
                        reason=f"网格卖出 获利层 @ {sell_price:.2f}",
                        score=65,
                        confidence=0.75
                    )
                    break
        
        # 更新网格位置
        grid_state['last_grid_idx'] = current_grid_idx
        
        # 定期检查是否需要重置网格（价格偏离中心太远）
        center_price = grid_state['center_price']
        deviation = abs(current_price - center_price) / center_price
        
        # 如果偏离超过 3 个网格，重置网格中心
        if deviation > self.grid_spacing * 3:
            self.grids[symbol] = {
                'center_price': current_price,
                'grids': self.calculate_grids(current_price),
                'last_grid_idx': self.get_grid_position(current_price, self.calculate_grids(current_price)),
                'buy_count': grid_state['buy_count'],
                'buy_prices': grid_state['buy_prices']
            }
            print(f"[{symbol}] 网格重置，新中心价格: {current_price:.2f}")
        
        return signal
    
    def reset_grid(self, symbol: str):
        """手动重置网格"""
        if symbol in self.grids:
            del self.grids[symbol]
    
    def get_grid_info(self, symbol: str) -> Optional[Dict]:
        """获取网格信息"""
        return self.grids.get(symbol)

# 全局实例
grid_strategy = GridTradingStrategy()
