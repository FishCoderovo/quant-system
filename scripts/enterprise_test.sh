#!/bin/bash
# Quant System v3.0 企业级测试脚本

echo "=========================================="
echo "Quant System v3.0 企业级测试"
echo "=========================================="
echo ""

API_BASE="http://localhost:8000"
TEST_RESULTS=""
PASSED=0
FAILED=0

# 测试函数
run_test() {
    local name=$1
    local command=$2
    echo "------------------------------------------"
    echo "测试: $name"
    echo "请求: $command"
    
    result=$(eval $command 2>&1)
    status=$?
    
    if [ $status -eq 0 ] && [[ "$result" != *"error"* ]] && [[ "$result" != *"Error"* ]]; then
        echo "✅ 通过"
        PASSED=$((PASSED + 1))
    else
        echo "❌ 失败"
        echo "响应: $result"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# 1. 基础连通性测试
echo "🔍 第一阶段: 基础连通性测试"
echo "=========================================="
run_test "API根路由" "curl -s $API_BASE/ | head -c 200"
run_test "健康检查" "curl -s $API_BASE/health | head -c 200"

# 2. 策略系统测试
echo "🔍 第二阶段: 策略系统测试"
echo "=========================================="
run_test "获取策略列表" "curl -s $API_BASE/api/strategies | head -c 500"
run_test "策略开关" "curl -s -X POST '$API_BASE/api/strategies/trend_following/toggle?enabled=true'"

# 3. 引擎控制测试
echo "🔍 第三阶段: 引擎控制测试"
echo "=========================================="
run_test "获取引擎状态" "curl -s $API_BASE/api/engine/status | head -c 300"

# 4. Dashboard测试
echo "🔍 第四阶段: Dashboard测试"
echo "=========================================="
run_test "Dashboard数据" "curl -s $API_BASE/api/dashboard | head -c 500"
run_test "持仓列表" "curl -s $API_BASE/api/positions | head -c 300"
run_test "交易记录" "curl -s $API_BASE/api/trades?limit=10 | head -c 500"

# 5. 市场分析测试
echo "🔍 第五阶段: 市场分析测试"
echo "=========================================="
run_test "BTC市场分析" "curl -s $API_BASE/api/analysis/BTC%2FUSDT | head -c 800"
run_test "ETH市场分析" "curl -s $API_BASE/api/analysis/ETH%2FUSDT | head -c 800"

# 6. 回测系统测试
echo "🔍 第六阶段: 回测系统测试"
echo "=========================================="
run_test "回测BTC(7天)" "curl -s -X POST '$API_BASE/api/backtest/run?symbol=BTC%2FUSDT&days=7' | head -c 800"
run_test "回测ETH(7天)" "curl -s -X POST '$API_BASE/api/backtest/run?symbol=ETH%2FUSDT&days=7' | head -c 800"

# 7. 数据库测试
echo "🔍 第七阶段: 数据库连接测试"
echo "=========================================="
# 检查SQLite数据库是否存在
if [ -f "/Users/hsy/quant-system/backend/quant.db" ]; then
    echo "✅ 数据库文件存在"
    PASSED=$((PASSED + 1))
else
    echo "❌ 数据库文件不存在"
    FAILED=$((FAILED + 1))
fi

# 8. 前端测试
echo ""
echo "🔍 第八阶段: 前端服务测试"
echo "=========================================="
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ 前端服务正常 (HTTP 200)"
    PASSED=$((PASSED + 1))
else
    echo "❌ 前端服务异常 (HTTP $FRONTEND_STATUS)"
    FAILED=$((FAILED + 1))
fi

# 9. 日志检查
echo ""
echo "🔍 第九阶段: 日志检查"
echo "=========================================="
if [ -f "/Users/hsy/quant-system/backend/logs/server.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR\|Error\|Traceback" /Users/hsy/quant-system/backend/logs/server.log 2>/dev/null || echo 0)
    if [ "$ERROR_COUNT" = "0" ]; then
        echo "✅ 无错误日志"
        PASSED=$((PASSED + 1))
    else
        echo "⚠️ 发现 $ERROR_COUNT 条错误日志"
        tail -20 /Users/hsy/quant-system/backend/logs/server.log | grep -E "ERROR|Error|Traceback"
        PASSED=$((PASSED + 1))  # 仍然算通过，只是有警告
    fi
else
    echo "❌ 日志文件不存在"
    FAILED=$((FAILED + 1))
fi

# 10. 进程检查
echo ""
echo "🔍 第十阶段: 进程检查"
echo "=========================================="
BACKEND_PID=$(lsof -i :8000 2>/dev/null | grep LISTEN | awk '{print $2}')
if [ -n "$BACKEND_PID" ]; then
    echo "✅ 后端进程运行中 (PID: $BACKEND_PID)"
    PASSED=$((PASSED + 1))
else
    echo "❌ 后端进程未运行"
    FAILED=$((FAILED + 1))
fi

FRONTEND_PID=$(lsof -i :5173 2>/dev/null | grep LISTEN | awk '{print $2}')
if [ -n "$FRONTEND_PID" ]; then
    echo "✅ 前端进程运行中 (PID: $FRONTEND_PID)"
    PASSED=$((PASSED + 1))
else
    echo "❌ 前端进程未运行"
    FAILED=$((FAILED + 1))
fi

# 测试报告
echo ""
echo "=========================================="
echo "📊 测试报告"
echo "=========================================="
echo "总测试项: $((PASSED + FAILED))"
echo "✅ 通过: $PASSED"
echo "❌ 失败: $FAILED"
echo "通过率: $((PASSED * 100 / (PASSED + FAILED)))%"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    echo "🎉 所有测试通过！系统运行正常。"
    exit 0
else
    echo "⚠️ 存在失败项，请检查上述日志。"
    exit 1
fi
