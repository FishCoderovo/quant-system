#!/bin/bash
# 启动后端服务

cd /Users/hsy/quant-system/backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "虚拟环境不存在，请先运行 init_backend.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: .env 文件不存在，请复制 .env.example 并配置"
    echo "  cp .env.example .env"
    exit 1
fi

# 启动服务
echo "启动 Quant System 后端服务..."
python3 -m app.main
