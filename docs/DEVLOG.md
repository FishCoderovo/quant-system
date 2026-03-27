# Quant System - 开发记录

## 项目目标
纯程序化、无需 AI 介入、分钟级量化交易系统

## 技术栈
- 后端: Python 3.11 + FastAPI + SQLite + APScheduler
- 前端: React + TailwindCSS
- 交易所: OKX

## 开发进度

### 2026-03-27 (完成)
- [x] 数据库模型设计 (SQLite + SQLAlchemy)
- [x] 数据收集器 (分钟级，APScheduler)
- [x] 策略引擎 (4种策略，自动切换)
- [x] 风控系统 (2%风险法则、ATR止损、移动止损)
- [x] 交易执行器 (自动买卖、止损止盈)
- [x] Web API (FastAPI)
- [x] 前端 Dashboard (React + Tailwind)

## 项目结构
```
quant-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI 主应用
│   │   ├── config.py        # 配置管理
│   │   ├── models.py        # 数据库模型
│   │   ├── exchange.py      # OKX API 封装
│   │   ├── indicators.py    # 技术指标计算
│   │   ├── strategy_engine.py  # 策略引擎
│   │   ├── trade_executor.py   # 交易执行器
│   │   ├── risk_manager.py     # 风控系统
│   │   ├── data_collector.py   # 数据收集器
│   │   ├── trading_engine.py   # 交易引擎
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── trend_following.py
│   │       ├── mean_reversion.py
│   │       ├── breakout.py
│   │       └── oversold_bounce.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   └── package.json
├── scripts/
│   ├── init_backend.sh
│   ├── start_backend.sh
│   └── graceful_shutdown.sh
└── docs/
    ├── PRD.md
    ├── DESIGN.md
    ├── API.md
    └── DEVLOG.md
```

## 策略复用
从旧系统 tradebot 复用:
- TrendFollowing (趋势跟随)
- MeanReversion (均值回归)
- Breakout (突破)
- OversoldBounce (超卖反弹)

风控照搬:
- 2% 风险法则
- 日亏损 -6 USDT 熔断
- ATR 动态止损
- 移动止损
- 多时间框架共振 (≥40分)
- 成交量确认 (≥80%)
