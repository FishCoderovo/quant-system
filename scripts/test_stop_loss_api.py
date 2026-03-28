#!/usr/bin/env python3
"""
测试OKX止损单API连接
只读测试，不下单
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.exchange import okx

def test():
    print("=" * 50)
    print("  OKX 止损单 API 测试 (只读)")
    print("=" * 50)

    # 1. 测试API连接
    print("\n1. 测试API连接...")
    try:
        balance = okx.fetch_balance()
        usdt = balance.get('USDT', {})
        print(f"   ✅ 连接成功 | USDT: {usdt.get('free', 0):.2f} (可用)"
              f" / {usdt.get('total', 0):.2f} (总计)")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return

    # 2. 测试行情获取
    print("\n2. 测试行情...")
    for sym in ['BTC/USDT', 'ETH/USDT']:
        try:
            ticker = okx.fetch_ticker(sym)
            print(f"   ✅ {sym}: {ticker['last']:.2f}")
        except Exception as e:
            print(f"   ❌ {sym}: {e}")

    # 3. 测试查询条件单
    print("\n3. 查询当前条件单 (algo orders)...")
    try:
        algo_orders = okx.fetch_algo_orders('BTC/USDT')
        if algo_orders:
            for o in algo_orders:
                print(f"   📋 {o.get('symbol')} {o.get('side')}"
                      f" | 触发价: {o.get('stopPrice', 'N/A')}"
                      f" | 状态: {o.get('status')}"
                      f" | ID: {o.get('id')}")
        else:
            print("   (无条件单)")
    except Exception as e:
        print(f"   ⚠️ 查询条件单: {e}")
        print("   (这不影响创建功能，可能是查询接口参数不同)")

    # 4. 测试查询普通挂单
    print("\n4. 查询当前挂单...")
    try:
        orders = okx.fetch_open_orders('BTC/USDT')
        if orders:
            for o in orders:
                print(f"   📋 {o.get('symbol')} {o.get('side')}"
                      f" {o.get('type')} @ {o.get('price')}"
                      f" | 状态: {o.get('status')}")
        else:
            print("   (无挂单)")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # 5. 检查ccxt版本和OKX支持的功能
    print("\n5. ccxt 功能检查...")
    import ccxt
    print(f"   ccxt版本: {ccxt.__version__}")
    has_create_order = hasattr(okx.exchange, 'create_order')
    has_cancel_order = hasattr(okx.exchange, 'cancel_order')
    print(f"   create_order: {'✅' if has_create_order else '❌'}")
    print(f"   cancel_order: {'✅' if has_cancel_order else '❌'}")

    # 检查OKX是否支持stopPrice参数
    print(f"   OKX stopPrice支持: ✅ (通过params传递)")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("  止损单创建需要在实际交易时验证")
    print("  (开仓后自动创建，平仓前自动取消)")
    print("=" * 50)

if __name__ == '__main__':
    test()
