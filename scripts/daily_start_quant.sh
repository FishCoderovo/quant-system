#!/bin/bash
# daily_start_quant.sh - 06:15 启动 Quant System 交易引擎

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 Quant System..."

LOG_FILE="$HOME/.openclaw/workspace-tradebot/logs/quant_start.log"
mkdir -p "$(dirname "$LOG_FILE")"

# 确保代理在运行
if ! pgrep -x "clash-verge" > /dev/null 2>&1; then
    echo "[$(date)] 启动 Clash Verge..." | tee -a "$LOG_FILE"
    open -a "Clash Verge" --hide 2>/dev/null || true
    sleep 5
fi

# 等待代理就绪
for i in {1..10}; do
    if curl -s http://127.0.0.1:7897 > /dev/null 2>&1; then
        echo "[$(date)] 代理已就绪" | tee -a "$LOG_FILE"
        break
    fi
    echo "[$(date)] 等待代理... ($i/10)" | tee -a "$LOG_FILE"
    sleep 2
done

# 启动 openclaw gateway
echo "[$(date)] 启动 openclaw gateway..." | tee -a "$LOG_FILE"
openclaw gateway restart 2>&1 | tail -3 >> "$LOG_FILE"
sleep 3

# 启动 quant-system 后端
echo "[$(date)] 启动 quant-system 后端..." | tee -a "$LOG_FILE"
cd "$HOME/quant-system/backend"

# 检查是否已在运行
if lsof -i :8001 > /dev/null 2>&1; then
    echo "[$(date)] ⚠️ 后端已在运行" | tee -a "$LOG_FILE"
else
    nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > "$HOME/quant-system/logs/backend.log" 2>&1 &
echo "[$(date)] ✅ 后端已启动 (PID: $!)" | tee -a "$LOG_FILE"
    
    # 等待后端就绪
    sleep 5
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "[$(date)] ✅ 后端健康检查通过" | tee -a "$LOG_FILE"
        
        # 启动交易引擎
        sleep 2
        curl -s -X POST http://localhost:8001/api/engine/start > /dev/null 2>&1
        echo "[$(date)] ✅ 交易引擎已启动" | tee -a "$LOG_FILE"
    else
        echo "[$(date)] ❌ 后端启动失败" | tee -a "$LOG_FILE"
    fi
fi

echo "[$(date)] 启动流程完成" | tee -a "$LOG_FILE"
