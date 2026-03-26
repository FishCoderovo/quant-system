#!/bin/bash
# Quant System - 一键启动脚本

echo "🚀 Starting Quant System..."

# Check if backend is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Backend already running on port 8000"
else
    echo "📦 Starting backend..."
    cd backend
    source venv/bin/activate 2>/dev/null || echo "⚠️  Virtual env not found, using system Python"
    python -m app.main &
    BACKEND_PID=$!
    cd ..
    echo "✅ Backend started (PID: $BACKEND_PID)"
fi

# Check if frontend is already running
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Frontend already running on port 5173"
else
    echo "🎨 Starting frontend..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
fi

echo ""
echo "📊 Quant System is running!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

wait
