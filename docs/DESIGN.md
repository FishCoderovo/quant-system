# Quant System - 设计文档

## 1. 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web 前端       │◀───▶│   FastAPI 后端   │◀───▶│   策略引擎       │
│  (React)        │ HTTP │  (REST API)     │      │  (异步执行)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         │              ┌─────────────────┐     ┌─────────────────┐
         │              │   SQLite        │     │   OKX API       │
         └─────────────▶│  (价格/交易)     │     │  (行情/下单)     │
                        └─────────────────┘     └─────────────────┘
```

## 2. 模块设计

### 2.1 数据收集器 (Data Collector)

**职责:** 每分钟拉取行情数据
**实现:** 定时任务 (APScheduler)
**存储:** SQLite (prices 表)

```python
# 核心逻辑
every minute:
    for symbol in [BTC, ETH, SOL, DOGE]:
        ticker = okx.fetch_ticker(symbol)
        ohlcv = okx.fetch_ohlcv(symbol, '1m', limit=200)
        save_to_db(ticker, ohlcv)
```

### 2.2 策略引擎 (Strategy Engine)

**职责:** 评估市场状态，生成交易信号
**实现:** 策略类 + 市场状态判定器

```python
class StrategyEngine:
    def run(self):
        market_state = self.detect_market_state()
        strategy = self.select_strategy(market_state)
        
        for symbol in symbols:
            signal = strategy.evaluate(symbol)
            if signal:
                self.execute(signal)
```

### 2.3 执行器 (Executor)

**职责:** 风控检查 + 下单执行
**流程:**
1. 检查风控（仓位、日亏损、冷却）
2. 计算仓位大小
3. 下单
4. 记录交易

### 2.4 Web API

**职责:** 提供数据查询接口
**关键接口:**
- `GET /api/dashboard` - Dashboard 数据
- `GET /api/positions` - 持仓列表
- `GET /api/trades` - 交易记录
- `GET /api/strategies` - 策略状态
- `POST /api/strategies/{id}/toggle` - 开关策略

### 2.5 前端

**路由:**
- `/` - Dashboard
- `/positions` - 持仓
- `/trades` - 交易记录
- `/strategies` - 策略配置
- `/logs` - 系统日志

## 3. 数据库设计

### 3.1 表结构

```sql
-- 价格数据
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,  -- '1m', '1h', etc
    timestamp INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 持仓
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'long', 'short'
    amount REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    stop_loss REAL,
    take_profit REAL,
    unrealized_pnl REAL,
    opened_at DATETIME,
    updated_at DATETIME
);

-- 交易记录
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'buy', 'sell'
    amount REAL NOT NULL,
    price REAL NOT NULL,
    value REAL NOT NULL,
    realized_pnl REAL,
    strategy TEXT,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 策略配置
CREATE TABLE strategy_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT 1,
    params TEXT,  -- JSON
    updated_at DATETIME
);

-- 系统状态
CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME
);
```

### 3.2 索引

```sql
CREATE INDEX idx_prices_symbol_time ON prices(symbol, timestamp);
CREATE INDEX idx_trades_created ON trades(created_at);
CREATE INDEX idx_positions_symbol ON positions(symbol);
```

## 4. 策略设计

### 4.1 基类

```python
from abc import ABC, abstractmethod

class Strategy(ABC):
    @abstractmethod
    def evaluate(self, symbol: str, data: DataFrame) -> Signal:
        """返回交易信号或 None"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

### 4.2 具体策略

见 `backend/app/strategies/` 目录

## 5. 风险控制设计

### 5.1 检查点

1. **前置检查**（信号生成后，执行前）
   - 日亏损是否超过限额
   - 是否处于交易冷却期
   - 当前仓位是否超过限制

2. **仓位计算**
   - 基于风险金额和止损距离计算
   - 不超过单次最大仓位限制

3. **止损管理**
   - 开仓时设置止损价
   - 定期更新移动止损

### 5.2 熔断机制

```python
if daily_loss > DAILY_LOSS_LIMIT:
    disable_trading_for_today()
```

## 6. 部署设计

### 6.1 本地运行

```bash
# 启动后端
cd backend
pip install -r requirements.txt
python -m app.main

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

### 6.2 进程管理

使用 `supervisor` 或 `pm2` 管理后台进程

### 6.3 数据备份

SQLite 文件定期备份到 `~/backups/`

## 7. 监控与告警

### 7.1 日志

- 应用日志: `logs/app.log`
- 交易日志: `logs/trades.log`
- 错误日志: `logs/errors.log`

### 7.2 健康检查

- `/health` 接口
- 定期检查交易所连接、数据库连接

## 8. 扩展性设计

### 8.1 策略扩展

新增策略只需:
1. 继承 `Strategy` 基类
2. 实现 `evaluate` 方法
3. 注册到策略引擎

### 8.2 交易所扩展

通过 CCXT 统一接口，切换交易所只需修改配置

### 8.3 数据库迁移

使用 SQLAlchemy ORM，SQLite → PostgreSQL 无需改代码
