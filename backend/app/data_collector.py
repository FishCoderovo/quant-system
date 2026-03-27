"""
数据收集器 - 每分钟收集行情数据
"""
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from app.models import SessionLocal, Price
from app.exchange import okx
from app.indicators import calculate_all_indicators
from app.config import settings

class DataCollector:
    """数据收集器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
    
    def collect_data(self):
        """收集所有币种数据"""
        db = SessionLocal()
        try:
            for symbol in settings.SYMBOLS:
                try:
                    # 获取 1 分钟 K 线数据
                    df = okx.fetch_ohlcv(symbol, '1m', limit=200)
                    
                    if df.empty:
                        continue
                    
                    # 计算指标
                    df = calculate_all_indicators(df)
                    
                    # 获取最新数据
                    latest = df.iloc[-1]
                    
                    # 保存到数据库
                    price = Price(
                        symbol=symbol,
                        timeframe='1m',
                        timestamp=int(latest['timestamp'].timestamp()),
                        open=latest['open'],
                        high=latest['high'],
                        low=latest['low'],
                        close=latest['close'],
                        volume=latest['volume']
                    )
                    
                    db.add(price)
                    
                except Exception as e:
                    print(f"[{datetime.now()}] 收集 {symbol} 数据失败: {e}")
                    continue
            
            db.commit()
            print(f"[{datetime.now()}] 数据收集完成")
            
        except Exception as e:
            print(f"[{datetime.now()}] 数据收集出错: {e}")
            db.rollback()
        finally:
            db.close()
    
    def start(self):
        """启动数据收集器"""
        if not self.is_running:
            # 立即执行一次
            self.collect_data()
            
            # 每分钟执行
            self.scheduler.add_job(
                self.collect_data,
                trigger=IntervalTrigger(seconds=settings.DATA_COLLECTION_INTERVAL),
                id='data_collector',
                name='Data Collector',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            print(f"[{datetime.now()}] 数据收集器已启动")
    
    def stop(self):
        """停止数据收集器"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print(f"[{datetime.now()}] 数据收集器已停止")
    
    def get_status(self):
        """获取状态"""
        return {
            'is_running': self.is_running,
            'next_run': self.scheduler.get_job('data_collector').next_run_time if self.is_running else None
        }

# 全局数据收集器实例
data_collector = DataCollector()
