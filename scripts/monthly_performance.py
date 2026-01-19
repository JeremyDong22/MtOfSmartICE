#!/usr/bin/env python3
"""Calculate average monthly performance for all stores in database."""

import sqlite3
from collections import defaultdict
from datetime import datetime

conn = sqlite3.connect('database/meituan_data.db')
cursor = conn.cursor()

# Get all business summary data
cursor.execute("""
    SELECT store_name, business_date, revenue, order_count, diner_count,
           per_capita_after_discount, avg_order_after_discount
    FROM mt_business_summary
    ORDER BY store_name, business_date
""")

store_data = defaultdict(lambda: {
    'total_revenue': 0,
    'total_orders': 0,
    'total_diners': 0,
    'days': 0,
    'dates': []
})

for row in cursor.fetchall():
    store_name, date, revenue, orders, diners, per_capita, avg_order = row
    store_data[store_name]['total_revenue'] += revenue or 0
    store_data[store_name]['total_orders'] += orders or 0
    store_data[store_name]['total_diners'] += diners or 0
    store_data[store_name]['days'] += 1
    store_data[store_name]['dates'].append(date)

conn.close()

print("=" * 120)
print("MONTHLY PERFORMANCE ANALYSIS - ALL STORES")
print(f"Data as of: 2026-01-16")
print("=" * 120)
print()

results = []
for store_name, data in store_data.items():
    if data['days'] == 0:
        continue

    # Calculate date range
    dates = sorted(data['dates'])
    start_date = datetime.strptime(dates[0], '%Y-%m-%d')
    end_date = datetime.strptime(dates[-1], '%Y-%m-%d')
    days_span = (end_date - start_date).days + 1
    months = days_span / 30.44  # Average days per month

    result = {
        'store_name': store_name,
        'total_revenue': data['total_revenue'],
        'total_orders': data['total_orders'],
        'total_diners': data['total_diners'],
        'days_tracked': data['days'],
        'date_range': f"{dates[0]} to {dates[-1]}",
        'months': months,
        'monthly_revenue': data['total_revenue'] / months if months > 0 else 0,
        'monthly_orders': data['total_orders'] / months if months > 0 else 0,
        'monthly_diners': data['total_diners'] / months if months > 0 else 0,
        'daily_revenue': data['total_revenue'] / data['days'],
        'daily_orders': data['total_orders'] / data['days'],
        'avg_order_value': data['total_revenue'] / data['total_orders'] if data['total_orders'] > 0 else 0
    }
    results.append(result)

# Sort by monthly revenue
results.sort(key=lambda x: x['monthly_revenue'], reverse=True)

print(f"{'Rank':<5} {'Store Name':<35} {'Monthly Rev':<15} {'Monthly Orders':<15} {'Avg Order':<12}")
print(f"{'':5} {'':35} {'(¥)':<15} {'Count':<15} {'Value (¥)':<12}")
print("-" * 120)

for i, r in enumerate(results, 1):
    print(f"{i:<5} {r['store_name']:<35} {r['monthly_revenue']:<15,.0f} "
          f"{r['monthly_orders']:<15,.0f} {r['avg_order_value']:<12,.0f}")

print()
print("=" * 120)
print("DETAILED METRICS")
print("=" * 120)
print()

for i, r in enumerate(results, 1):
    print(f"{i}. {r['store_name']}")
    print(f"   Period: {r['date_range']} ({r['days_tracked']} days, {r['months']:.1f} months)")
    print(f"   Total Revenue: ¥{r['total_revenue']:,.0f}")
    print(f"   Total Orders: {r['total_orders']:,}")
    print(f"   Total Diners: {r['total_diners']:,}")
    print(f"   Monthly Avg Revenue: ¥{r['monthly_revenue']:,.0f}")
    print(f"   Monthly Avg Orders: {r['monthly_orders']:,.0f}")
    print(f"   Monthly Avg Diners: {r['monthly_diners']:,.0f}")
    print(f"   Daily Avg Revenue: ¥{r['daily_revenue']:,.0f}")
    print(f"   Daily Avg Orders: {r['daily_orders']:,.0f}")
    print(f"   Avg Order Value: ¥{r['avg_order_value']:,.0f}")
    print()

# Summary statistics
total_monthly_revenue = sum(r['monthly_revenue'] for r in results)
avg_monthly_revenue = total_monthly_revenue / len(results) if results else 0

print("=" * 120)
print("SUMMARY STATISTICS")
print("=" * 120)
print(f"Total Stores: {len(results)}")
print(f"Combined Monthly Revenue: ¥{total_monthly_revenue:,.0f}")
print(f"Average Monthly Revenue per Store: ¥{avg_monthly_revenue:,.0f}")
print(f"Top Performer: {results[0]['store_name']} (¥{results[0]['monthly_revenue']:,.0f}/month)")
print(f"Lowest Performer: {results[-1]['store_name']} (¥{results[-1]['monthly_revenue']:,.0f}/month)")
print()
