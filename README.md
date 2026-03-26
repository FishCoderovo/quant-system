# 量化交易系统

加密货币量化交易系统，支持分钟级自动交易，Web 可视化监控。

## 特性

- ⚡ 分钟级策略执行
- 📊 Web 可视化 Dashboard
- 🔄 多策略自动切换
- 🛡️ 完整风险控制
- 📈 收益率曲线追踪

## 技术栈

- **后端:** Python 3.11 + FastAPI + SQLite
- **前端:** React + TailwindCSS
- **交易所:** OKX

## 文档

- [需求文档](./docs/PRD.md)
- [设计文档](./docs/DESIGN.md)
- [接口文档](./docs/API.md)

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/FishCoderovo/quant-system.git
cd quant-system

# 启动后端
cd backend
pip install -r requirements.txt
python -m app.main

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 警告

⚠️ 量化交易存在亏损风险，请谨慎使用。
