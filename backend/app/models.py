"""
数据库模型
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

Base = declarative_base()
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Price(Base):
    """价格数据表"""
    __tablename__ = "prices"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)  # 1m, 1h, 4h, 1d
    timestamp = Column(Integer, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Position(Base):
    """持仓表"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # long, short
    amount = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    unrealized_pnl = Column(Float)
    realized_pnl = Column(Float, default=0)
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_open = Column(Boolean, default=True)
    strategy = Column(String(50))  # 开仓策略
    atr = Column(Float)  # 开仓时的ATR值

class Trade(Base):
    """交易记录表"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy, sell
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    value = Column(Float, nullable=False)
    realized_pnl = Column(Float)
    pnl_pct = Column(Float)
    strategy = Column(String(50))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class StrategyConfig(Base):
    """策略配置表"""
    __tablename__ = "strategy_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
    params = Column(Text)  # JSON 字符串
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemState(Base):
    """系统状态表"""
    __tablename__ = "system_state"
    
    key = Column(String(50), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DailyStats(Base):
    """每日统计"""
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), unique=True, nullable=False)  # YYYY-MM-DD
    total_pnl = Column(Float, default=0)
    trade_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
