-- Quant System Database Schema

-- 价格数据
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prices_symbol_time ON prices(symbol, timestamp);

-- 持仓
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    amount REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    stop_loss REAL,
    take_profit REAL,
    unrealized_pnl REAL,
    opened_at DATETIME,
    updated_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);

-- 交易记录
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    amount REAL NOT NULL,
    price REAL NOT NULL,
    value REAL NOT NULL,
    realized_pnl REAL,
    strategy TEXT,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);

-- 策略配置
CREATE TABLE IF NOT EXISTS strategy_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT 1,
    params TEXT,
    updated_at DATETIME
);

-- 系统状态
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME
);

-- 初始化系统状态
INSERT OR IGNORE INTO system_state (key, value, updated_at) VALUES 
    ('version', '0.1.0', CURRENT_TIMESTAMP),
    ('status', 'stopped', CURRENT_TIMESTAMP),
    ('daily_loss', '0', CURRENT_TIMESTAMP);
