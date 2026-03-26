"""
Quant System - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Quant System API",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/dashboard")
async def dashboard():
    """Dashboard 数据"""
    return {
        "total_balance": 0,
        "available_balance": 0,
        "positions_value": 0,
        "today_pnl": 0,
        "today_pnl_percent": 0,
        "total_return": 0,
        "active_positions": 0,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
