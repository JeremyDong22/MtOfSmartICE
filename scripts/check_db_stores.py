#!/usr/bin/env python3
"""Check what stores are in the database."""

import sqlite3

conn = sqlite3.connect('database/meituan_data.db')
cursor = conn.cursor()

print("Stores in mt_business_summary:")
cursor.execute("SELECT DISTINCT store_name FROM mt_business_summary ORDER BY store_name")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

print("\nSample data from mt_business_summary:")
cursor.execute("SELECT store_name, business_date, revenue, order_count FROM mt_business_summary ORDER BY business_date DESC LIMIT 10")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} - ¥{row[2]:,.0f} ({row[3]} orders)")

conn.close()
