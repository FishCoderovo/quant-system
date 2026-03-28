#!/usr/bin/env python3
"""
回测脚本 v3.0 — 双向交易版 (做多+做空)
核心改动:
1. 做空: 下跌趋势做空赚钱 (合约1x无杠杆)
2. 做多: 上涨趋势做多 (现货)
3. 合约手续费: maker 0.02% (比现货0.08%便宜)
4. 双向止损止盈 + 移动止损
5. 连续亏损保护 (连亏3笔暂停8天)
6. 180天数据覆盖完整牛熊
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
def fetch_ohlcv(symbol: str, timeframe: str = '4h', days: int = 180) -> pd.DataFrame:
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


# ─── 市场状态检测 v3 ─────────────────────────────────────────
def detect_market_state(df: pd.DataFrame) -> str:
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

    if ma5 > 0 and ma10 > 0 and ma20 > 0:
        if ma5 < ma10 < ma20:
            return "strong_downtrend" if chg20 < -5 else "downtrend"
        if ma5 > ma10 > ma20:
            return "strong_uptrend" if chg20 > 5 else "uptrend"

    if ma20 > 0 and price < ma20 and len(df) >= 25:
        ma20_prev = df['close'].iloc[-25:-5].mean()
        if ma20 < ma20_prev:
            return "downtrend"

    if ma20 > 0 and price > ma20 and len(df) >= 25:
        ma20_prev = df['close'].iloc[-25:-5].mean()
        if ma20 > ma20_prev and chg5 > 0.5:
            return "uptrend"

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


# ─── 策略映射 (双向: 上涨做多, 下跌做空) ─────────────────────
STRATEGY_MAP = {
    'strong_uptrend': ['trend_following', 'turtle'],
    'uptrend': ['trend_following', 'turtle'],
    'range_bound': [],
    'high_volatility': ['turtle'],
    'downtrend': ['trend_following', 'turtle'],       # 做空
    'strong_downtrend': ['trend_following', 'turtle'], # 做空
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

        # 分类信号
        buys = [(s, w) for s, w in signals if s.action == 'buy']
        shorts = [(s, w) for s, w in signals if s.action == 'short']
        sells = [(s, w) for s, w in signals if s.action == 'sell']
        covers = [(s, w) for s, w in signals if s.action == 'cover']

        # 做多信号
        bs = sum(s.score * w for s, w in buys)
        # 做空信号
        ss = sum(s.score * w for s, w in shorts)
        # 平多信号
        sell_s = sum(s.score * w for s, w in sells)
        # 平空信号
        cover_s = sum(s.score * w for s, w in covers)

        # 优先级: 平仓 > 开仓
        if sell_s > SELL_THRESHOLD and sells:
            return max(sells, key=lambda x: x[0].score)[0]
        if cover_s > SELL_THRESHOLD and covers:
            return max(covers, key=lambda x: x[0].score)[0]

        # 开仓: 做多 vs 做空，选更强的
        if bs > ss and bs > BUY_THRESHOLD and buys:
            return max(buys, key=lambda x: x[0].score)[0]
        if ss > bs and ss > BUY_THRESHOLD and shorts:
            return max(shorts, key=lambda x: x[0].score)[0]
        if bs > BUY_THRESHOLD and buys:
            return max(buys, key=lambda x: x[0].score)[0]
        if ss > BUY_THRESHOLD and shorts:
            return max(shorts, key=lambda x: x[0].score)[0]

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
        f"  策略: TrendFollowing + Turtle (双向交易)",
        f"  做多手续费: 0.08% | 做空手续费: 0.02% (合约)",
        f"  止损: ATR×2.5 | 盈亏比: 2.5:1 | 移动止损: ✅",
        f"{'─'*60}",
        f"  总收益率:     {r.total_return*100:>+8.2f}%",
        f"  年化收益率:   {r.annualized_return*100:>+8.2f}%",
        f"  夏普比率:     {r.sharpe_ratio:>8.2f}",
        f"  最大回撤:     {r.max_drawdown*100:>8.2f}%",
        f"{'─'*60}",
        f"  总交易:       {r.total_trades}笔 (做多{r.long_trades} + 做空{r.short_trades})",
        f"  胜率:         {r.win_rate*100:>8.2f}%",
        f"  盈亏比:       {r.profit_factor:>8.2f}",
        f"  平均盈利:     {r.avg_profit:>+8.4f} USDT",
        f"  平均亏损:     {r.avg_loss:>8.4f} USDT",
        f"  总手续费:     {r.total_fees:>8.4f} USDT",
        f"{'─'*60}",
        f"  做多盈亏:     {r.long_pnl:>+8.4f} USDT ({r.long_trades}笔)",
        f"  做空盈亏:     {r.short_pnl:>+8.4f} USDT ({r.short_trades}笔)",
        f"{'─'*60}",
    ]
    closes = [t for t in r.trades if t.action in ('sell', 'cover')]
    if closes:
        sl = sum(1 for t in closes if '止损' in t.reason)
        tp = sum(1 for t in closes if '止盈' in t.reason)
        ot = len(closes) - sl - tp
        lines.append(f"  出场统计:  止损{sl} | 止盈{tp} | 策略{ot}")
        lines.append(f"{'─'*60}")
        show = min(15, len(closes))
        lines.append(f"  全部 {len(closes)} 笔平仓:")
        for t in closes:
            d = '📈' if t.direction == 'long' else '📉'
            e = '✅' if t.pnl > 0 else '❌'
            ts = t.timestamp.strftime('%m-%d %H:%M') if hasattr(t.timestamp, 'strftime') else str(t.timestamp)
            lines.append(f"    {d}{e} {ts} | {t.strategy:15s} | PnL: {t.pnl:+.4f} ({t.pnl_pct*100:+.2f}%) | {t.reason[:40]}")
    else:
        lines.append(f"  无交易")
    lines.append(f"{'='*60}")
    return '\n'.join(lines)


def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║   Quant System 回测 v3.0 (双向交易版)                ║")
    print("║   ⬆️ 上涨做多 (现货) + ⬇️ 下跌做空 (合约1x)         ║")
    print("║   策略: TrendFollowing + Turtle                      ║")
    print("║   币种: BTC + ETH                                    ║")
    print("║   数据: 4h K线 ~180天                                ║")
    print("║   止损: ATR×2.5 + 移动止损                           ║")
    print("║   盈亏比: 2.5:1                                      ║")
    print("║   初始资金: 58 USDT                                  ║")
    print("╚══════════════════════════════════════════════════════╝")

    symbols = ['BTC/USDT', 'ETH/USDT']
    all_results = {}

    for sym in symbols:
        print(f"\n⏳ 拉取 {sym} 4h K线 (~180天)...")
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
            'long_trades': r.long_trades,
            'short_trades': r.short_trades,
            'long_pnl': f"{r.long_pnl:+.4f} USDT",
            'short_pnl': f"{r.short_pnl:+.4f} USDT",
            'total_fees': f"{r.total_fees:.4f} USDT",
        }

    if all_results:
        print(f"\n{'═'*65}")
        print(f"  汇总")
        print(f"{'═'*65}")
        for sym, res in all_results.items():
            print(f"  {sym:12s} | {res['total_return']:>8s} | WR {res['win_rate']:>6s} | PF {res['profit_factor']:>5s} | DD {res['max_drawdown']:>6s} | {res['total_trades']}笔(L{res['long_trades']}+S{res['short_trades']})")
        print(f"{'═'*65}")

    out = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_results.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'version': 'v3.0',
            'config': {
                'initial_balance': 58.0,
                'timeframe': '4h',
                'period': '~180 days',
                'spot_fee': 'maker 0.08%',
                'contract_fee': 'maker 0.02%',
                'stop_loss': 'ATR×2.5 + trailing (both directions)',
                'take_profit': 'R:R 2.5:1',
                'position_sizing': '2% risk, max 70%',
                'market_detection': 'MA alignment + price vs MA20',
                'strategies': ['TrendFollowing', 'Turtle'],
                'symbols': ['BTC/USDT', 'ETH/USDT'],
                'long_mode': 'spot',
                'short_mode': 'contract 1x (no leverage)',
                'consecutive_loss_protection': '3 losses → 8 day cooldown',
            },
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n📊 结果已保存: {os.path.abspath(out)}")
    print("🏁 回测完成!")


if __name__ == '__main__':
    main()
