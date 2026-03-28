#!/usr/bin/env python3
"""
数据库迁移: 给 positions 表加 stop_loss_order_id 和 take_profit_order_id 字段
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'quant.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}，跳过迁移（首次启动时会自动创建）")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(positions)")
    columns = [col[1] for col in cursor.fetchall()]

    added = []
    if 'stop_loss_order_id' not in columns:
        cursor.execute("ALTER TABLE positions ADD COLUMN stop_loss_order_id VARCHAR(64)")
        added.append('stop_loss_order_id')

    if 'take_profit_order_id' not in columns:
        cursor.execute("ALTER TABLE positions ADD COLUMN take_profit_order_id VARCHAR(64)")
        added.append('take_profit_order_id')

    conn.commit()
    conn.close()

    if added:
        print(f"✅ 迁移完成: 添加了 {', '.join(added)}")
    else:
        print("✅ 字段已存在，无需迁移")

if __name__ == '__main__':
    migrate()
