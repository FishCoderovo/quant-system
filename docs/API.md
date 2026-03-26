# Quant System - 接口文档 (API)

## 基础信息

- **Base URL:** `http://localhost:8000`
- **Content-Type:** `application/json`

## 接口列表

### Dashboard

#### GET /api/dashboard
获取 Dashboard 概览数据

**Response:**
```json
{
  "total_balance": 100.50,
  "available_balance": 40.50,
  "positions_value": 60.00,
  "today_pnl": 5.20,
  "today_pnl_percent": 5.46,
  "total_return": 12.50,
  "active_positions": 1,
  "last_trade_at": "2024-01-15T10:30:00",
  "market_summary": [
    {"symbol": "BTC/USDT", "price": 45000, "change_24h": 2.5},
    {"symbol": "ETH/USDT", "price": 2800, "change_24h": -1.2}
  ]
}
```

---

### 持仓

#### GET /api/positions
获取当前持仓列表

**Response:**
```json
{
  "positions": [
    {
      "id": 1,
      "symbol": "SOL/USDT",
      "side": "long",
      "amount": 0.4655,
      "entry_price": 88.04,
      "current_price": 92.50,
      "stop_loss": 87.06,
      "take_profit": 88.76,
      "unrealized_pnl": 2.08,
      "unrealized_pnl_percent": 5.07,
      "opened_at": "2024-01-15T10:30:00"
    }
  ]
}
```

---

### 交易记录

#### GET /api/trades
获取交易历史

**Query Parameters:**
- `limit` (int): 返回数量，默认 50
- `offset` (int): 偏移量，默认 0
- `symbol` (string): 筛选币种，可选

**Response:**
```json
{
  "total": 100,
  "trades": [
    {
      "id": 1,
      "symbol": "SOL/USDT",
      "side": "buy",
      "amount": 0.4655,
      "price": 88.04,
      "value": 40.98,
      "realized_pnl": null,
      "strategy": "MeanReversion",
      "reason": "RSI 14.7 + BB -8.3%",
      "created_at": "2024-01-15T10:30:00"
    },
    {
      "id": 2,
      "symbol": "SOL/USDT",
      "side": "sell",
      "amount": 0.4655,
      "price": 92.50,
      "value": 43.06,
      "realized_pnl": 2.08,
      "strategy": "MeanReversion",
      "reason": "止盈平仓",
      "created_at": "2024-01-15T14:30:00"
    }
  ]
}
```

#### GET /api/trades/stats
获取交易统计

**Response:**
```json
{
  "total_trades": 50,
  "win_count": 30,
  "loss_count": 20,
  "win_rate": 60.0,
  "avg_profit": 2.5,
  "avg_loss": -1.8,
  "profit_factor": 2.08,
  "total_pnl": 45.20
}
```

---

### 策略

#### GET /api/strategies
获取策略列表

**Response:**
```json
{
  "strategies": [
    {
      "id": "trend_following",
      "name": "TrendFollowing",
      "enabled": true,
      "description": "趋势跟随策略",
      "params": {
        "ma_fast": 5,
        "ma_slow": 20,
        "rsi_min": 40,
        "rsi_max": 70
      }
    },
    {
      "id": "mean_reversion",
      "name": "MeanReversion",
      "enabled": true,
      "description": "均值回归策略",
      "params": {
        "rsi_threshold": 50,
        "bb_threshold": 45
      }
    }
  ],
  "current_strategy": "MeanReversion",
  "market_state": "区间震荡"
}
```

#### POST /api/strategies/{id}/toggle
切换策略开关

**Request:**
```json
{
  "enabled": false
}
```

**Response:**
```json
{
  "success": true,
  "strategy_id": "trend_following",
  "enabled": false
}
```

#### PUT /api/strategies/{id}/params
更新策略参数

**Request:**
```json
{
  "params": {
    "rsi_threshold": 45
  }
}
```

---

### 系统

#### GET /api/system/status
获取系统状态

**Response:**
```json
{
  "status": "running",
  "version": "0.1.0",
  "uptime": 3600,
  "exchange_connected": true,
  "last_scan_at": "2024-01-15T14:35:00",
  "daily_stats": {
    "trades_count": 5,
    "daily_pnl": 3.20,
    "daily_loss_limit": -6.00,
    "remaining_limit": 9.20
  }
}
```

#### GET /api/system/logs
获取系统日志

**Query Parameters:**
- `level` (string): 日志级别 (info, warning, error)
- `limit` (int): 返回数量，默认 100

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2024-01-15T14:30:00",
      "level": "info",
      "message": "策略扫描完成，无信号"
    },
    {
      "timestamp": "2024-01-15T14:29:00",
      "level": "info",
      "message": "MeanReversion 生成买入信号 SOL/USDT"
    }
  ]
}
```

#### POST /api/system/pause
暂停交易

**Response:**
```json
{
  "success": true,
  "status": "paused"
}
```

#### POST /api/system/resume
恢复交易

**Response:**
```json
{
  "success": true,
  "status": "running"
}
```

---

### 收益率曲线

#### GET /api/performance/equity
获取权益曲线数据

**Query Parameters:**
- `days` (int): 天数，默认 30

**Response:**
```json
{
  "data": [
    {"date": "2024-01-01", "equity": 100.00},
    {"date": "2024-01-02", "equity": 102.50},
    {"date": "2024-01-03", "equity": 101.80}
  ]
}
```

---

## 错误响应

**格式:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "参数验证失败",
    "details": {
      "field": "amount",
      "message": "必须大于0"
    }
  }
}
```

**HTTP 状态码:**
- `200` - 成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误
