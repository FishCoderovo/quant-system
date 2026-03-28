#!/bin/bash
# nightly_close.sh - 22:45 强制清仓脚本
# 模式: 保守版 - 不持仓过夜

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行夜间清仓..."

LOG_FILE="$HOME/.openclaw/workspace-tradebot/logs/nightly_close.log"
mkdir -p "$(dirname "$LOG_FILE")"

# 检查后端是否运行
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "[$(date)] ❌ 后端未运行，无法清仓" | tee -a "$LOG_FILE"
    # 尝试通过飞书通知
    echo "❌ 清仓失败: 后端未运行" >&2
    exit 1
fi

# 调用API强制清仓所有持仓
echo "[$(date)] 调用API清仓..." | tee -a "$LOG_FILE"

RESULT=$(curl -s -X POST http://localhost:8001/api/positions/close-all \
    -H "Content-Type: application/json" \
    -d '{"reason": "夜间强制平仓 - 不持仓过夜"}' 2>&1)

echo "[$(date)] API响应: $RESULT" | tee -a "$LOG_FILE"

# 检查是否有持仓（验证清仓成功）
sleep 2
POSITIONS=$(curl -s http://localhost:8001/api/positions 2>/dev/null | grep -c '"symbol"' || echo "0")

if [ "$POSITIONS" -eq "0" ]; then
    echo "[$(date)] ✅ 清仓完成，当前无持仓" | tee -a "$LOG_FILE"
    echo "✅ 夜间清仓完成 | 当前无持仓" >&2
    exit 0
else
    echo "[$(date)] ⚠️ 清仓后仍有 $POSITIONS 个持仓" | tee -a "$LOG_FILE"
    echo "⚠️ 清仓异常 | 仍有 $POSITIONS 个持仓" >&2
    exit 1
fi
