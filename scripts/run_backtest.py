#!/usr/bin/env python3
"""
回测脚本 - 直接调用回测引擎，不依赖API
"""
import sys
sys.path.insert(0, '/Users/hsy/quant-system/backend')

import json
from datetime import datetime

# 导入模块
from app.exchange import okx
from app.backtest_engine import backtest_engine
from app.strategy_engine import strategy_engine
from app.indicators import calculate_all_indicators

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']
DAYS = 30
TIMEFRAME = '1h'

print("=" * 60)
print(f"📊 Quant System v3.1 回测报告")
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📅 回测周期: {DAYS}天 | 时间框架: {TIMEFRAME}")
print(f"💰 初始资金: 10,000 USDT")
print("=" * 60)

results = []

for symbol in SYMBOLS:
    print(f"\n🔍 正在回测 {symbol}...")
    
    try:
        # 获取历史数据
        limit = min(DAYS * 24, 720)  # 1h线，30天=720根
        df = okx.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
        
        if df.empty or len(df) < 50:
            print(f"  ❌ 数据不足 ({len(df)} 根K线)")
            continue
        
        print(f"  📈 获取到 {len(df)} 根K线")
        
        # 计算指标
        df = calculate_all_indicators(df)
        
        # 运行回测
        result = backtest_engine.run_backtest(
            df,
            lambda s, d: strategy_engine.evaluate_symbol(s, d),
            symbol
        )
        
        r = {
            'symbol': symbol,
            'total_return': result.total_return * 100,
            'annualized_return': result.annualized_return * 100,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown * 100,
            'win_rate': result.win_rate * 100,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades
        }
        results.append(r)
        
        print(f"  ✅ 完成")
        print(f"     收益: {r['total_return']:+.2f}%")
        print(f"     夏普比率: {r['sharpe_ratio']:.2f}")
        print(f"     最大回撤: {r['max_drawdown']:.2f}%")
        print(f"     胜率: {r['win_rate']:.1f}%")
        print(f"     总交易数: {r['total_trades']}")
        print(f"     盈利因子: {r['profit_factor']:.2f}")
        
    except Exception as e:
        print(f"  ❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()

# 汇总
print("\n" + "=" * 60)
print("📊 回测汇总")
print("=" * 60)

if results:
    print(f"\n{'币种':<12} {'收益':>8} {'夏普':>6} {'回撤':>8} {'胜率':>6} {'交易数':>6} {'盈利因子':>8}")
    print("-" * 60)
    for r in results:
        print(f"{r['symbol']:<12} {r['total_return']:>+7.2f}% {r['sharpe_ratio']:>6.2f} {r['max_drawdown']:>7.2f}% {r['win_rate']:>5.1f}% {r['total_trades']:>6} {r['profit_factor']:>8.2f}")
    
    # 平均值
    avg_return = sum(r['total_return'] for r in results) / len(results)
    avg_sharpe = sum(r['sharpe_ratio'] for r in results) / len(results)
    avg_dd = sum(r['max_drawdown'] for r in results) / len(results)
    avg_wr = sum(r['win_rate'] for r in results) / len(results)
    total_trades = sum(r['total_trades'] for r in results)
    
    print("-" * 60)
    print(f"{'平均':<12} {avg_return:>+7.2f}% {avg_sharpe:>6.2f} {avg_dd:>7.2f}% {avg_wr:>5.1f}% {total_trades:>6}")
    
    # 评级
    print("\n📈 系统评级:")
    if avg_return > 5:
        print("  🟢 盈利能力: 优秀")
    elif avg_return > 0:
        print("  🟡 盈利能力: 一般")
    else:
        print("  🔴 盈利能力: 亏损")
    
    if avg_sharpe > 1.5:
        print("  🟢 风险调整收益: 优秀")
    elif avg_sharpe > 0.5:
        print("  🟡 风险调整收益: 一般")
    else:
        print("  🔴 风险调整收益: 差")
    
    if avg_dd < 5:
        print("  🟢 回撤控制: 优秀")
    elif avg_dd < 15:
        print("  🟡 回撤控制: 一般")
    else:
        print("  🔴 回撤控制: 差")
    
    if avg_wr > 55:
        print("  🟢 胜率: 优秀")
    elif avg_wr > 45:
        print("  🟡 胜率: 一般")
    else:
        print("  🔴 胜率: 低")

else:
    print("❌ 没有成功完成任何回测")

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'period_days': DAYS,
    'timeframe': TIMEFRAME,
    'initial_capital': 10000,
    'results': results
}

with open('/Users/hsy/quant-system/backend/data/backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n💾 结果已保存到 data/backtest_results.json")

print("\n" + "=" * 60)
print("回测完成！")
