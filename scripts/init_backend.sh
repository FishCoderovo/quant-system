#!/bin/bash
# 初始化数据库脚本

cd /Users/hsy/quant-system/backend

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 初始化数据库
echo "初始化数据库..."
python3 -c "
from app.models import init_db
init_db()
print('数据库初始化完成')
"

echo "初始化完成！"
echo ""
echo "启动命令:"
echo "  source venv/bin/activate"
echo "  python3 -m app.main"
