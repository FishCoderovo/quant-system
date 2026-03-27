"""
FastAPI 主应用
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from app.config import settings
from app.models import init_db, get_db, Position, Trade, DailyStats
from app.trading_engine import trading_engine
from app.strategy_engine import strategy_engine
from app.exchange import okx

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    init_db()
    print("数据库已初始化")
    yield
    # 关闭时停止交易引擎
    if trading_engine.is_running:
        trading_engine.stop()
        print("交易引擎已停止")

app = FastAPI(
    title=settings.APP_NAME,
    description="加密货币量化交易系统",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ API 路由 ============

@app.get("/")
async def root():
    """根路由"""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "trading_engine": trading_engine.get_status()
    }

@app.post("/api/engine/start")
async def start_engine():
    """启动交易引擎"""
    if not trading_engine.is_running:
        trading_engine.start()
        return {"status": "started"}
    return {"status": "already_running"}

@app.post("/api/engine/stop")
async def stop_engine():
    """停止交易引擎"""
    if trading_engine.is_running:
        trading_engine.stop()
        return {"status": "stopped"}
    return {"status": "already_stopped"}

@app.get("/api/engine/status")
async def get_engine_status():
    """获取引擎状态"""
    return trading_engine.get_status()

@app.get("/api/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """获取 Dashboard 数据"""
    # 获取账户余额
    try:
        balance = okx.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('total', 0)
        usdt_free = balance.get('USDT', {}).get('free', 0)
    except:
        usdt_balance = 0
        usdt_free = 0
    
    # 获取持仓
    positions = db.query(Position).filter(Position.is_open == True).all()
    position_list = [{
        'id': p.id,
        'symbol': p.symbol,
        'amount': p.amount,
        'entry_price': p.entry_price,
        'current_price': p.current_price,
        'unrealized_pnl': p.unrealized_pnl,
        'stop_loss': p.stop_loss,
        'take_profit': p.take_profit
    } for p in positions]
    
    # 获取今日统计
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    daily_stats = db.query(DailyStats).filter(DailyStats.date == today).first()
    
    return {
        'total_balance': usdt_balance,
        'available_balance': usdt_free,
        'positions_count': len(positions),
        'positions': position_list,
        'market_state': strategy_engine.market_state,
        'active_strategy': strategy_engine.active_strategy,
        'daily_pnl': daily_stats.total_pnl if daily_stats else 0,
        'daily_trades': daily_stats.trade_count if daily_stats else 0
    }

@app.get("/api/positions")
async def get_positions(db: Session = Depends(get_db)):
    """获取持仓列表"""
    positions = db.query(Position).filter(Position.is_open == True).all()
    return [{
        'id': p.id,
        'symbol': p.symbol,
        'side': p.side,
        'amount': p.amount,
        'entry_price': p.entry_price,
        'current_price': p.current_price,
        'stop_loss': p.stop_loss,
        'take_profit': p.take_profit,
        'unrealized_pnl': p.unrealized_pnl,
        'opened_at': p.opened_at,
        'strategy': p.strategy
    } for p in positions]

@app.get("/api/trades")
async def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    """获取交易记录"""
    trades = db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()
    return [{
        'id': t.id,
        'symbol': t.symbol,
        'side': t.side,
        'amount': t.amount,
        'price': t.price,
        'value': t.value,
        'realized_pnl': t.realized_pnl,
        'pnl_pct': t.pnl_pct,
        'strategy': t.strategy,
        'reason': t.reason,
        'created_at': t.created_at
    } for t in trades]

@app.get("/api/strategies")
async def get_strategies():
    """获取策略状态"""
    return strategy_engine.get_strategy_status()

@app.post("/api/strategies/{strategy_name}/toggle")
async def toggle_strategy(strategy_name: str, enabled: bool):
    """开关策略"""
    strategy_engine.toggle_strategy(strategy_name, enabled)
    return {"status": "success", "strategy": strategy_name, "enabled": enabled}

# ============ 回测 API ============

@app.post("/api/backtest/run")
async def run_backtest(
    symbol: str = "BTC/USDT",
    days: int = 30,
    strategy: str = "all"
):
    """
    运行回测
    
    参数:
    - symbol: 交易对
    - days: 回测天数
    - strategy: 策略名或 'all'
    """
    from app.backtest_engine import backtest_engine
    from app.exchange import okx
    import pandas as pd
    
    try:
        # 获取历史数据
        timeframe = '1h' if days <= 30 else '4h'
        limit = min(days * 24, 1000) if timeframe == '1h' else min(days * 6, 500)
        
        df = okx.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if df.empty or len(df) < 50:
            return {"error": "历史数据不足"}
        
        # 运行回测
        from app.strategy_engine import strategy_engine as se
        result = backtest_engine.run_backtest(
            df, 
            lambda s, d: se.evaluate_symbol(s, d),
            symbol
        )
        
        return {
            "symbol": symbol,
            "period_days": days,
            "total_return": f"{result.total_return*100:.2f}%",
            "annualized_return": f"{result.annualized_return*100:.2f}%",
            "sharpe_ratio": f"{result.sharpe_ratio:.2f}",
            "max_drawdown": f"{result.max_drawdown*100:.2f}%",
            "win_rate": f"{result.win_rate*100:.2f}%",
            "profit_factor": f"{result.profit_factor:.2f}",
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "equity_curve": result.equity_curve[-100:]  # 最近100个点
        }
    
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/analysis/{symbol}")
async def get_market_analysis(symbol: str):
    """
    获取市场综合分析
    
    返回:
    - 量价背离分析
    - Wyckoff周期
    - 综合评分
    """
    from app.exchange import okx
    from app.strategy_engine import strategy_engine
    
    try:
        # 获取数据
        df = okx.fetch_ohlcv(symbol, '1h', limit=100)
        
        if df.empty:
            return {"error": "无法获取数据"}
        
        # 运行分析
        analysis = strategy_engine.analyze_market(symbol, df)
        
        return {
            "symbol": symbol,
            "timestamp": analysis.get('timestamp', pd.Timestamp.now()).isoformat() if hasattr(analysis.get('timestamp'), 'isoformat') else str(analysis.get('timestamp')),
            "market_state": analysis.get('market_state', 'unknown'),
            "composite_score": analysis.get('composite_score', 0),
            "signals": analysis.get('signals', []),
            "divergence": analysis.get('divergence'),
            "wyckoff": analysis.get('wyckoff')
        }
    
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
