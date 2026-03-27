"""
交易引擎 - 核心交易循环
"""
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from app.models import SessionLocal, Position
from app.exchange import okx
from app.strategy_engine import strategy_engine
from app.trade_executor import TradeExecutor
from app.data_collector import data_collector
from app.indicators import calculate_all_indicators
from app.config import settings

class TradingEngine:
    """交易引擎"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.executor = None
    
    def run_strategy_cycle(self):
        """执行一轮策略循环"""
        db = SessionLocal()
        try:
            self.executor = TradeExecutor(db)
            
            for symbol in settings.SYMBOLS:
                try:
                    # 1. 获取最新数据
                    df = okx.fetch_ohlcv(symbol, '1m', limit=200)
                    
                    if df.empty:
                        continue
                    
                    # 2. 计算指标
                    df = calculate_all_indicators(df)
                    
                    # 3. 检查现有持仓的卖出条件
                    sell_results = self.executor.check_and_execute_sells(
                        symbol, df['close'].iloc[-1]
                    )
                    
                    for result in sell_results:
                        if result.get('success'):
                            print(f"[{datetime.now()}] 卖出: {result}")
                    
                    # 4. 执行策略评估
                    signal = strategy_engine.evaluate_symbol(symbol, df)
                    
                    if signal is None:
                        continue
                    
                    print(f"[{datetime.now()}] 信号: {signal.to_dict()}")
                    
                    # 5. 执行买入
                    if signal.action == 'buy':
                        latest = df.iloc[-1]
                        result = self.executor.execute_buy(
                            symbol=signal.symbol,
                            strategy=signal.strategy,
                            reason=signal.reason,
                            entry_price=latest['close'],
                            atr=latest.get('atr', latest['close'] * 0.02)
                        )
                        
                        if result.get('success'):
                            print(f"[{datetime.now()}] 买入成功: {result}")
                        else:
                            print(f"[{datetime.now()}] 买入失败: {result.get('error')}")
                
                except Exception as e:
                    print(f"[{datetime.now()}] 处理 {symbol} 出错: {e}")
                    continue
        
        except Exception as e:
            print(f"[{datetime.now()}] 策略循环出错: {e}")
        finally:
            db.close()
    
    def start(self):
        """启动交易引擎"""
        if not self.is_running:
            # 启动数据收集器
            data_collector.start()
            
            # 每秒执行一次策略循环
            self.scheduler.add_job(
                self.run_strategy_cycle,
                trigger=IntervalTrigger(seconds=settings.STRATEGY_EXECUTION_INTERVAL),
                id='trading_engine',
                name='Trading Engine',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            print(f"[{datetime.now()}] 交易引擎已启动")
    
    def stop(self):
        """停止交易引擎"""
        if self.is_running:
            self.scheduler.shutdown()
            data_collector.stop()
            self.is_running = False
            print(f"[{datetime.now()}] 交易引擎已停止")
    
    def get_status(self):
        """获取状态"""
        return {
            'is_running': self.is_running,
            'market_state': strategy_engine.market_state,
            'active_strategy': strategy_engine.active_strategy,
            'data_collector': data_collector.get_status()
        }

# 全局交易引擎实例
trading_engine = TradingEngine()
