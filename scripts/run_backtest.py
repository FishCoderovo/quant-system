#!/usr/bin/env python3
"""
回测脚本 v2.3 — 终极精简版
核心改动:
1. 只保留2个趋势策略 (TrendFollowing + Turtle)
2. 超强趋势过滤 (MA排列 + 价格vs MA20 + MA20斜率)
3. 只交易 BTC 和 ETH (SOL波动太大，小资金扛不住)
4. 只在上涨趋势做多，其余全部空仓
5. 分批拉取90天4h数据
6. ATR×2.5 止损 + 移动止损
7. 盈亏比 2.5:1 (纯趋势策略)
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import ccxt
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

from app.backtest_engine import BacktestEngine
from app.indicators import calculate_all_indicators
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.turtle import TurtleStrategy
from app.config import settings


# ─── 分批拉取数据 ────────────────────────────────────────────
def fetch_ohlcv(symbol: str, timeframe: str = '4h', days: int = 90) -> pd.DataFrame:
    exchange = ccxt.okx({
        'enableRateLimit': True,
        'proxies': {
            'http': settings.OKX_PROXY,
            'https': settings.OKX_PROXY,
        }
    })
    all_ohlcv = []
    target_start_ms = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    since = target_start_ms
    batch = 0
    while True:
        batch += 1
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=300)
        if not ohlcv:
            break
        all_ohlcv.extend(ohlcv)
        last_ts = ohlcv[-1][0]
        since = last_ts + 1
        print(f"      批次{batch}: +{len(ohlcv)}根 (至 {pd.Timestamp(last_ts, unit='ms')})")
        if len(ohlcv) < 300:
            break
        time.sleep(0.3)
    if not all_ohlcv:
        raise ValueError(f"未获取到 {symbol} 数据")
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.drop_duplicates(subset='timestamp', keep='first', inplace=True)
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df


# ─── 市场状态检测 v3: 超强趋势过滤 ──────────────────────────
def detect_market_state(df: pd.DataFrame) -> str:
    """与 strategy_engine.py 完全同步"""
    if len(df) < 30:
        return "unknown"
    latest = df.iloc[-1]
    price = df['close'].iloc[-1]
    p5 = df['close'].iloc[-5] if len(df) >= 5 else df['close'].iloc[0]
    p20 = df['close'].iloc[-20] if len(df) >= 20 else df['close'].iloc[0]
    chg5 = (price - p5) / p5 * 100
    chg20 = (price - p20) / p20 * 100
    atr_pct = latest.get('atr', price * 0.01) / price
    vol_ratio = latest.get('volume_ratio', 1.0)
    bb_w = latest.get('bb_width', 0.1)
    ma5 = latest.get('ma5', 0)
    ma10 = latest.get('ma10', 0)
    ma20 = latest.get('ma20', 0)

    # 1. MA排列 (最高优先级)
    if ma5 > 0 and ma10 > 0 and ma20 > 0:
        if ma5 < ma10 < ma20:
            return "strong_downtrend" if chg20 < -5 else "downtrend"
        if ma5 > ma10 > ma20:
            return "strong_uptrend" if chg20 > 5 else "uptrend"

    # 2. 价格<MA20 + MA20下降 → 下跌
    if ma20 > 0 and price < ma20 and len(df) >= 25:
        ma20_prev = df['close'].iloc[-25:-5].mean()
        if ma20 < ma20_prev:
            return "downtrend"

    # 3. 价格>MA20 + MA20上升 → 上涨
    if ma20 > 0 and price > ma20 and len(df) >= 25:
        ma20_prev = df['close'].iloc[-25:-5].mean()
        if ma20 > ma20_prev and chg5 > 0.5:
            return "uptrend"

    # 4. 涨跌幅兜底
    if chg5 > 2 or chg20 > 5:
        return "strong_uptrend"
    elif chg5 < -2 or chg20 < -5:
        return "strong_downtrend"
    elif chg5 < -0.5 or chg20 < -2:
        return "downtrend"
    elif atr_pct > 0.02 and vol_ratio > 1.5:
        return "high_volatility"
    elif bb_w < 0.03:
        return "low_volatility"
    return "range_bound"


# ─── 策略映射 (终极精简，只在上涨做多) ──────────────────────
STRATEGY_MAP = {
    'strong_uptrend': ['trend_following', 'turtle'],
    'uptrend': ['trend_following', 'turtle'],
    'range_bound': [],
    'high_volatility': ['turtle'],
    'downtrend': [],
    'strong_downtrend': [],
    'low_volatility': [],
}

WEIGHTS = {
    'trend_following': 1.2,
    'turtle': 1.3,
}

BUY_THRESHOLD = 60
SELL_THRESHOLD = 50


def make_strategy_func(strats):
    def func(symbol, df):
        if len(df) < 30:
            return None
        ms = detect_market_state(df)
        active = STRATEGY_MAP.get(ms, [])
        if not active:
            return None
        signals = []
        for name in active:
            if name in strats:
                sig = strats[name].evaluate(symbol, df)
                if sig:
                    signals.append((sig, WEIGHTS.get(name, 1.0)))
        if not signals:
            return None
        buys = [(s, w) for s, w in signals if s.action == 'buy']
        sells = [(s, w) for s, w in signals if s.action == 'sell']
        bs = sum(s.score * w for s, w in buys)
        ss = sum(s.score * w for s, w in sells)
        if bs > ss and bs > BUY_THRESHOLD:
            return max(buys, key=lambda x: x[0].score)[0]
        elif ss > SELL_THRESHOLD:
            return max(sells, key=lambda x: x[0].score)[0]
        return None
    return func


def run_single(symbol, df, balance=58.0):
    strats = {
        'trend_following': TrendFollowingStrategy(),
        'turtle': TurtleStrategy(),
    }
    engine = BacktestEngine(initial_balance=balance, fee_type='maker')
    return engine.run_backtest(df, make_strategy_func(strats), symbol)


def fmt_result(symbol, r, df):
    t0 = df.index[0].strftime('%Y-%m-%d %H:%M') if hasattr(df.index[0], 'strftime') else '?'
    t1 = df.index[-1].strftime('%Y-%m-%d %H:%M') if hasattr(df.index[-1], 'strftime') else '?'
    days = (df.index[-1] - df.index[0]).days if hasattr(df.index[0], 'day') else len(df) // 6
    final_bal = r.equity_curve[-1] if r.equity_curve else 58.0
    lines = [
        f"\n{'='*60}",
        f"  {symbol} 回测报告",
        f"{'='*60}",
        f"  周期: {t0} → {t1} ({days}天, {len(df)}根4h K线)",
        f"  初始: 58.00 USDT → 最终: {final_bal:.2f} USDT",
        f"  策略: TrendFollowing + Turtle (纯趋势)",
        f"  手续费: maker 0.08% | 止损: ATR×2.5 | R:R 2.5:1",
        f"{'─'*60}",
        f"  总收益率:     {r.total_return*100:>+8.2f}%",
        f"  年化收益率:   {r.annualized_return*100:>+8.2f}%",
        f"  夏普比率:     {r.sharpe_ratio:>8.2f}",
        f"  最大回撤:     {r.max_drawdown*100:>8.2f}%",
        f"{'─'*60}",
        f"  交易次数:     {r.total_trades}",
        f"  胜率:         {r.win_rate*100:>8.2f}%",
        f"  盈亏比:       {r.profit_factor:>8.2f}",
        f"  平均盈利:     {r.avg_profit:>+8.4f} USDT",
        f"  平均亏损:     {r.avg_loss:>8.4f} USDT",
        f"  总手续费:     {r.total_fees:>8.4f} USDT",
        f"{'─'*60}",
    ]
    sells = [t for t in r.trades if t.action == 'sell']
    if sells:
        sl = sum(1 for t in sells if '止损' in t.reason)
        tp = sum(1 for t in sells if '止盈' in t.reason)
        ot = len(sells) - sl - tp
        lines.append(f"  出场统计:  止损{sl} | 止盈{tp} | 策略{ot}")
        lines.append(f"{'─'*60}")
        show = min(10, len(sells))
        lines.append(f"  全部 {len(sells)} 笔卖出:")
        for t in sells:
            e = '✅' if t.pnl > 0 else '❌'
            ts = t.timestamp.strftime('%m-%d %H:%M') if hasattr(t.timestamp, 'strftime') else str(t.timestamp)
            lines.append(f"    {e} {ts} | {t.strategy:15s} | PnL: {t.pnl:+.4f} ({t.pnl_pct*100:+.2f}%) | {t.reason[:45]}")
    else:
        lines.append(f"  无交易 (全程空仓 — 无上涨趋势信号)")
    lines.append(f"{'='*60}")
    return '\n'.join(lines)


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   Quant System 回测 v2.3 (终极精简版)            ║")
    print("║   策略: TrendFollowing + Turtle                  ║")
    print("║   币种: BTC + ETH (砍掉SOL)                     ║")
    print("║   数据: 4h K线 ~180天 (覆盖完整牛熊周期)        ║")
    print("║   入场: 只在上涨趋势做多，其余空仓              ║")
    print("║   止损: ATR×2.5 + 移动止损                      ║")
    print("║   盈亏比: 2.5:1                                 ║")
    print("║   手续费: maker 0.08%                           ║")
    print("║   初始资金: 58 USDT                             ║")
    print("╚══════════════════════════════════════════════════╝")

    symbols = ['BTC/USDT', 'ETH/USDT']  # 砍掉SOL
    all_results = {}

    for sym in symbols:
        print(f"\n⏳ 拉取 {sym} 4h K线 (~180天, 覆盖完整牛熊)...")
        try:
            df = fetch_ohlcv(sym, '4h', days=180)
            days = (df.index[-1] - df.index[0]).days if len(df) > 1 else 0
            print(f"   ✅ 共 {len(df)} 根K线 ({days}天)")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            continue
        print(f"⏳ 运行回测...")
        r = run_single(sym, df)
        print(fmt_result(sym, r, df))
        final_bal = r.equity_curve[-1] if r.equity_curve else 58.0
        all_results[sym] = {
            'total_return': f"{r.total_return*100:.2f}%",
            'final_balance': f"{final_bal:.2f} USDT",
            'win_rate': f"{r.win_rate*100:.2f}%",
            'profit_factor': f"{r.profit_factor:.2f}",
            'max_drawdown': f"{r.max_drawdown*100:.2f}%",
            'sharpe_ratio': f"{r.sharpe_ratio:.2f}",
            'total_trades': r.total_trades,
            'total_fees': f"{r.total_fees:.4f} USDT",
            'winning': r.winning_trades,
            'losing': r.losing_trades,
        }

    if all_results:
        print(f"\n{'═'*60}")
        print(f"  汇总")
        print(f"{'═'*60}")
        for sym, res in all_results.items():
            print(f"  {sym:12s} | {res['total_return']:>8s} | WR {res['win_rate']:>6s} | PF {res['profit_factor']:>5s} | DD {res['max_drawdown']:>6s} | {res['total_trades']}笔")
        print(f"{'═'*60}")

    out = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_results.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'version': 'v2.3',
            'config': {
                'initial_balance': 58.0,
                'timeframe': '4h',
                'period': '~90 days',
                'fee': 'maker 0.08%',
                'stop_loss': 'ATR×2.5 + trailing',
                'take_profit': 'R:R 2.5:1',
                'position_sizing': '2% risk, max 70%',
                'market_detection': 'MA alignment + price vs MA20 + MA20 slope',
                'buy_threshold': BUY_THRESHOLD,
                'strategies': ['TrendFollowing', 'Turtle'],
                'symbols': ['BTC/USDT', 'ETH/USDT'],
                'downtrend_action': 'no trade (100% cash)',
            },
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n📊 结果已保存: {os.path.abspath(out)}")
    print("🏁 回测完成!")


if __name__ == '__main__':
    main()
