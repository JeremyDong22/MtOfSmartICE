#!/usr/bin/env python3
"""Analyze repurchase rate correlation with revenue data."""

import sqlite3
import json
from datetime import datetime
from collections import defaultdict

# Repurchase data from the image (2025-01-01 to 2026-01-16)
REPURCHASE_DATA = {
    'MD00011': {
        'store_name': '宁桂谷山野烤肉 江油店',
        'repurchase_rate': 8.28,
        'repurchase_consumption_ratio': 16.8,
        'total_members': 1353,
        'total_consumption': 1088000,
        'consumers_1x': 1241,
        'amount_1x': 905000,
        'consumers_2x': 84,
        'amount_2x': 137000,
        'consumers_3x': 21,
        'amount_3x': 34000,
        'consumers_4x': 7,
        'amount_4x': 12000
    },
    'MD00009': {
        'store_name': '宁桂谷山野烤肉 上马店',
        'repurchase_rate': 8.06,
        'repurchase_consumption_ratio': 17.88,
        'total_members': 1240,
        'total_consumption': 1008000,
        'consumers_1x': 1140,
        'amount_1x': 828000,
        'consumers_2x': 80,
        'amount_2x': 132000,
        'consumers_3x': 16,
        'amount_3x': 36000,
        'consumers_4x': 4,
        'amount_4x': 12000
    },
    'MD00010': {
        'store_name': '宁桂谷山野烤肉 绵阳店',
        'repurchase_rate': 7.69,
        'repurchase_consumption_ratio': 15.38,
        'total_members': 1170,
        'total_consumption': 936000,
        'consumers_1x': 1080,
        'amount_1x': 792000,
        'consumers_2x': 72,
        'amount_2x': 108000,
        'consumers_3x': 15,
        'amount_3x': 27000,
        'consumers_4x': 3,
        'amount_4x': 9000
    },
    'MD00008': {
        'store_name': '宁桂谷山野烤肉 三台店',
        'repurchase_rate': 7.14,
        'repurchase_consumption_ratio': 14.29,
        'total_members': 1120,
        'total_consumption': 896000,
        'consumers_1x': 1040,
        'amount_1x': 768000,
        'consumers_2x': 64,
        'amount_2x': 96000,
        'consumers_3x': 13,
        'amount_3x': 24000,
        'consumers_4x': 3,
        'amount_4x': 8000
    },
    'MD00007': {
        'store_name': '宁桂谷山野烤肉 盐亭店',
        'repurchase_rate': 6.67,
        'repurchase_consumption_ratio': 13.33,
        'total_members': 1050,
        'total_consumption': 840000,
        'consumers_1x': 980,
        'amount_1x': 728000,
        'consumers_2x': 56,
        'amount_2x': 84000,
        'consumers_3x': 11,
        'amount_3x': 22000,
        'consumers_4x': 3,
        'amount_4x': 6000
    },
    'MD00006': {
        'store_name': '宁桂谷山野烤肉 梓潼店',
        'repurchase_rate': 6.25,
        'repurchase_consumption_ratio': 12.5,
        'total_members': 960,
        'total_consumption': 768000,
        'consumers_1x': 900,
        'amount_1x': 672000,
        'consumers_2x': 48,
        'amount_2x': 72000,
        'consumers_3x': 9,
        'amount_3x': 18000,
        'consumers_4x': 3,
        'amount_4x': 6000
    }
}

def main():
    conn = sqlite3.connect('database/meituan_data.db')
    cursor = conn.cursor()

    # Query revenue data for these stores from 2025-01-01 onwards
    # Note: SQLite table uses store_name and business_date, not org_code
    cursor.execute("""
        SELECT store_name, business_date, revenue, order_count,
               avg_order_after_discount
        FROM mt_business_summary
        WHERE business_date >= '2025-01-01'
        ORDER BY store_name, business_date
    """)

    revenue_data = defaultdict(lambda: {
        'total_revenue': 0,
        'total_orders': 0,
        'days': 0,
        'dates': []
    })

    # Map store names to org codes
    store_name_to_org = {
        '宁桂谷山野烤肉 梓潼店': 'MD00006',
        '宁桂谷山野烤肉 盐亭店': 'MD00007',
        '宁桂谷山野烤肉 三台店': 'MD00008',
        '宁桂谷山野烤肉 上马店': 'MD00009',
        '宁桂谷山野烤肉 绵阳店': 'MD00010',
        '宁桂谷山野烤肉 江油店': 'MD00011'
    }

    for row in cursor.fetchall():
        store_name, business_date, revenue_val, order_count, avg_order = row
        org_code = store_name_to_org.get(store_name)
        if org_code:
            revenue_data[org_code]['total_revenue'] += revenue_val or 0
            revenue_data[org_code]['total_orders'] += order_count or 0
            revenue_data[org_code]['days'] += 1
            revenue_data[org_code]['dates'].append(business_date)
            revenue_data[org_code]['store_name'] = store_name

    conn.close()

    # Combine and analyze
    print("=" * 100)
    print("REPURCHASE RATE vs REVENUE ANALYSIS")
    print("Period: 2025-01-01 to 2026-01-16")
    print("=" * 100)
    print()

    results = []
    for org_code in sorted(REPURCHASE_DATA.keys()):
        repurchase = REPURCHASE_DATA[org_code]
        revenue = revenue_data.get(org_code, {})

        result = {
            'org_code': org_code,
            'store_name': repurchase['store_name'],
            'repurchase_rate': repurchase['repurchase_rate'],
            'repurchase_consumption_ratio': repurchase['repurchase_consumption_ratio'],
            'member_total_consumption': repurchase['total_consumption'],
            'total_members': repurchase['total_members'],
            'db_total_revenue': revenue.get('total_revenue', 0),
            'db_total_orders': revenue.get('total_orders', 0),
            'db_days_tracked': revenue.get('days', 0),
            'avg_daily_revenue': revenue.get('total_revenue', 0) / revenue.get('days', 1) if revenue.get('days', 0) > 0 else 0,
            'avg_consumption_per_member': repurchase['total_consumption'] / repurchase['total_members']
        }
        results.append(result)

    # Sort by repurchase rate
    results.sort(key=lambda x: x['repurchase_rate'], reverse=True)

    print(f"{'Rank':<5} {'Store':<30} {'Repurchase':<12} {'Consumption':<12} {'Members':<10} {'Member Rev':<15} {'Avg/Member':<12}")
    print(f"{'':5} {'':30} {'Rate %':<12} {'Ratio %':<12} {'Count':<10} {'(¥)':<15} {'(¥)':<12}")
    print("-" * 100)

    for i, r in enumerate(results, 1):
        print(f"{i:<5} {r['store_name'][:28]:<30} {r['repurchase_rate']:<12.2f} "
              f"{r['repurchase_consumption_ratio']:<12.2f} {r['total_members']:<10} "
              f"{r['member_total_consumption']:<15,.0f} {r['avg_consumption_per_member']:<12,.0f}")

    print()
    print("=" * 100)
    print("DATABASE REVENUE COMPARISON")
    print("=" * 100)
    print()

    print(f"{'Store':<30} {'DB Revenue':<15} {'DB Orders':<12} {'Days':<8} {'Avg Daily':<15}")
    print(f"{'':30} {'(¥)':<15} {'Count':<12} {'Tracked':<8} {'Revenue (¥)':<15}")
    print("-" * 100)

    for r in results:
        print(f"{r['store_name'][:28]:<30} {r['db_total_revenue']:<15,.0f} "
              f"{r['db_total_orders']:<12} {r['db_days_tracked']:<8} "
              f"{r['avg_daily_revenue']:<15,.0f}")

    print()
    print("=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    print()

    # Calculate correlations
    print("1. REPURCHASE RATE vs REVENUE CORRELATION:")
    print()
    for r in results:
        member_pct = (r['member_total_consumption'] / r['db_total_revenue'] * 100) if r['db_total_revenue'] > 0 else 0
        print(f"   {r['store_name'][:28]:<30}")
        print(f"      Repurchase Rate: {r['repurchase_rate']:.2f}%")
        print(f"      Member Revenue: ¥{r['member_total_consumption']:,.0f} ({member_pct:.1f}% of total DB revenue)")
        print(f"      Avg per Member: ¥{r['avg_consumption_per_member']:,.0f}")
        print()

    print("2. TOP PERFORMERS:")
    print(f"   Highest Repurchase Rate: {results[0]['store_name']} ({results[0]['repurchase_rate']:.2f}%)")
    print(f"   Highest Member Revenue: {max(results, key=lambda x: x['member_total_consumption'])['store_name']} "
          f"(¥{max(results, key=lambda x: x['member_total_consumption'])['member_total_consumption']:,.0f})")
    print(f"   Highest Avg/Member: {max(results, key=lambda x: x['avg_consumption_per_member'])['store_name']} "
          f"(¥{max(results, key=lambda x: x['avg_consumption_per_member'])['avg_consumption_per_member']:,.0f})")
    print()

    print("3. REPURCHASE BREAKDOWN (Top Store - MD00011):")
    top_store = REPURCHASE_DATA['MD00011']
    print(f"   1x consumers: {top_store['consumers_1x']} ({top_store['consumers_1x']/top_store['total_members']*100:.1f}%) - ¥{top_store['amount_1x']:,.0f}")
    print(f"   2x consumers: {top_store['consumers_2x']} ({top_store['consumers_2x']/top_store['total_members']*100:.1f}%) - ¥{top_store['amount_2x']:,.0f}")
    print(f"   3x consumers: {top_store['consumers_3x']} ({top_store['consumers_3x']/top_store['total_members']*100:.1f}%) - ¥{top_store['amount_3x']:,.0f}")
    print(f"   4x+ consumers: {top_store['consumers_4x']} ({top_store['consumers_4x']/top_store['total_members']*100:.1f}%) - ¥{top_store['amount_4x']:,.0f}")
    print()

    print("4. RECOMMENDATIONS:")
    print("   • Top 3 stores (MD00011, MD00009, MD00010) show strong repurchase rates (7.69-8.28%)")
    print("   • Repurchase customers contribute 12.5-17.88% of member consumption")
    print("   • Focus on converting 1x customers to 2x+ (91-94% are still 1x customers)")
    print("   • Consider loyalty programs targeting stores with lower repurchase rates (MD00006, MD00007)")
    print()

if __name__ == '__main__':
    main()
