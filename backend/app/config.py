"""
Quant System - 配置文件
"""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Quant System"
    DEBUG: bool = False
    
    # 数据库
    DATABASE_URL: str = "sqlite:///./quant.db"
    
    # OKX API 配置
    OKX_API_KEY: str = ""
    OKX_API_SECRET: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_PROXY: str = "http://127.0.0.1:7897"  # 代理设置
    OKX_SANDBOX: bool = False
    
    # 交易配置
    AVAILABLE_SYMBOLS: list = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]  # 支持的全部币种
    ENABLED_SYMBOLS: str = "BTC/USDT,ETH/USDT"  # 当前启用的币种（逗号分隔，可在.env覆盖）
    TIMEFRAMES: list = ["1m", "1h", "4h", "1d"]
    
    # 运行模式
    LONG_ONLY: bool = True  # 只做多，禁止做空（保守模式）
    LEVERAGE: int = 3  # 合约杠杆倍数（做空时使用）
    TRADE_MODE: str = "spot"  # spot=现货做多, cross=全仓合约, isolated=逐仓合约
    
    @property
    def SYMBOLS(self) -> list:
        """解析启用的币种列表"""
        return [s.strip() for s in self.ENABLED_SYMBOLS.split(",") if s.strip()]
    
    # 风控参数
    MAX_POSITION_PCT: float = 0.70  # 单次最大 70%
    MAX_SINGLE_RISK_PCT: float = 0.15  # 单笔风险 ≤ 15%
    MIN_RISK_REWARD_RATIO: float = 2.0  # 最小盈亏比 2.0:1 (从2.5降低，更容易触发止盈)
    VOLUME_CONFIRMATION_THRESHOLD: float = 0.80  # 成交量确认 (>80%)
    MULTI_TF_MIN_SCORE: int = 40  # 最小共振评分
    TRADE_COOLDOWN_MIN: int = 15  # 交易冷却 15分钟
    DAILY_LOSS_LIMIT: float = 6.0  # 日损失限制 (USDT)
    
    # 数据收集配置
    DATA_COLLECTION_INTERVAL: int = 60  # 数据收集间隔（秒）
    STRATEGY_EXECUTION_INTERVAL: int = 60  # 策略执行间隔（秒）
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
