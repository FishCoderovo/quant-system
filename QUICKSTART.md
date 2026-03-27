# Quant System 快速启动指南

## 1. 配置环境

### 后端配置
```bash
cd /Users/hsy/quant-system/backend

# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 OKX API 密钥
nano .env
```

### 前端依赖安装
```bash
cd /Users/hsy/quant-system/frontend
npm install
npm install recharts  # 图表库
```

## 2. 启动服务

### 终端 1: 启动后端
```bash
cd /Users/hsy/quant-system
./scripts/start_backend.sh

# 或者直接
source backend/venv/bin/activate
python3 -m backend.app.main
```
后端将运行在 http://localhost:8000

### 终端 2: 启动前端
```bash
cd /Users/hsy/quant-system/frontend
npm run dev
```
前端将运行在 http://localhost:5173

## 3. 使用系统

1. 打开浏览器访问 http://localhost:5173
2. 点击"启动引擎"按钮开始自动交易
3. Dashboard 显示资产、持仓、盈亏等信息

## 4. API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/engine/start | POST | 启动交易引擎 |
| /api/engine/stop | POST | 停止交易引擎 |
| /api/engine/status | GET | 获取引擎状态 |
| /api/dashboard | GET | 获取 Dashboard 数据 |
| /api/positions | GET | 获取持仓列表 |
| /api/trades | GET | 获取交易记录 |
| /api/strategies | GET | 获取策略状态 |

## 5. 策略说明

系统会根据市场状态自动切换策略：

| 市场状态 | 策略 |
|----------|------|
| 强劲上涨 | TrendFollowing (趋势跟随) |
| 上涨趋势 | TrendFollowing |
| 区间震荡 | MeanReversion (均值回归) |
| 高波动 | Breakout (突破) |
| 低波动/下跌 | 观望 |

## 6. 风控规则

- 单次最大仓位: 70%
- 单笔风险: ≤15%
- 日亏损限制: -6 USDT (触发后当日停止交易)
- 交易冷却: 15 分钟
- 最小盈亏比: 0.8:1

## 注意事项

⚠️ **风险提示**: 量化交易存在亏损风险，请谨慎使用。
- 先使用小额资金测试
- 确认策略表现稳定后再增加资金
- 定期检查系统运行状态
