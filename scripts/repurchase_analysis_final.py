#!/usr/bin/env python3
"""Analyze repurchase rate data from the member repurchase summary."""

# Repurchase data from the image (2025-01-01 to 2026-01-16)
# Brand: 宁桂谷山野烤肉 (Ning Gui Gu)
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
    print("=" * 120)
    print("MEMBER REPURCHASE ANALYSIS - 宁桂谷山野烤肉")
    print("Period: 2025-01-01 to 2026-01-16 (381 days)")
    print("=" * 120)
    print()

    # Sort by repurchase rate
    stores = sorted(REPURCHASE_DATA.items(), key=lambda x: x[1]['repurchase_rate'], reverse=True)

    # Summary table
    print(f"{'Rank':<5} {'Store':<25} {'Repurchase':<12} {'Consumption':<12} {'Members':<10} {'Total Rev':<15} {'Avg/Member':<12} {'Daily Avg':<12}")
    print(f"{'':5} {'':25} {'Rate %':<12} {'Ratio %':<12} {'Count':<10} {'(¥)':<15} {'(¥)':<12} {'(¥)':<12}")
    print("-" * 120)

    for i, (org_code, data) in enumerate(stores, 1):
        avg_per_member = data['total_consumption'] / data['total_members']
        daily_avg = data['total_consumption'] / 381
        print(f"{i:<5} {data['store_name']:<25} {data['repurchase_rate']:<12.2f} "
              f"{data['repurchase_consumption_ratio']:<12.2f} {data['total_members']:<10} "
              f"{data['total_consumption']:<15,.0f} {avg_per_member:<12,.0f} {daily_avg:<12,.0f}")

    print()
    print("=" * 120)
    print("DETAILED CUSTOMER SEGMENTATION")
    print("=" * 120)
    print()

    for i, (org_code, data) in enumerate(stores, 1):
        print(f"{i}. {data['store_name']} (Repurchase Rate: {data['repurchase_rate']}%)")
        print(f"   {'Segment':<15} {'Customers':<12} {'% of Total':<12} {'Revenue (¥)':<15} {'% of Revenue':<15} {'Avg/Customer':<12}")
        print(f"   {'-'*80}")

        segments = [
            ('1x visitors', data['consumers_1x'], data['amount_1x']),
            ('2x visitors', data['consumers_2x'], data['amount_2x']),
            ('3x visitors', data['consumers_3x'], data['amount_3x']),
            ('4x+ visitors', data['consumers_4x'], data['amount_4x'])
        ]

        for seg_name, count, amount in segments:
            pct_customers = count / data['total_members'] * 100
            pct_revenue = amount / data['total_consumption'] * 100
            avg_per_customer = amount / count if count > 0 else 0
            print(f"   {seg_name:<15} {count:<12} {pct_customers:<12.1f} {amount:<15,.0f} {pct_revenue:<15.1f} {avg_per_customer:<12,.0f}")

        print(f"   {'TOTAL':<15} {data['total_members']:<12} {'100.0':<12} {data['total_consumption']:<15,.0f} {'100.0':<15}")
        print()

    print("=" * 120)
    print("KEY INSIGHTS & RECOMMENDATIONS")
    print("=" * 120)
    print()

    # Calculate totals
    total_members = sum(d['total_members'] for d in REPURCHASE_DATA.values())
    total_revenue = sum(d['total_consumption'] for d in REPURCHASE_DATA.values())
    avg_repurchase_rate = sum(d['repurchase_rate'] for d in REPURCHASE_DATA.values()) / len(REPURCHASE_DATA)

    print(f"OVERALL METRICS:")
    print(f"  • Total Members: {total_members:,}")
    print(f"  • Total Member Revenue: ¥{total_revenue:,.0f}")
    print(f"  • Average Repurchase Rate: {avg_repurchase_rate:.2f}%")
    print(f"  • Daily Average Revenue: ¥{total_revenue/381:,.0f}")
    print()

    print("1. REPURCHASE RATE PERFORMANCE:")
    print(f"   • Top Performer: {stores[0][1]['store_name']} ({stores[0][1]['repurchase_rate']:.2f}%)")
    print(f"   • Lowest Performer: {stores[-1][1]['store_name']} ({stores[-1][1]['repurchase_rate']:.2f}%)")
    print(f"   • Gap: {stores[0][1]['repurchase_rate'] - stores[-1][1]['repurchase_rate']:.2f} percentage points")
    print()

    print("2. CUSTOMER RETENTION CHALLENGE:")
    avg_1x_pct = sum(d['consumers_1x'] / d['total_members'] * 100 for d in REPURCHASE_DATA.values()) / len(REPURCHASE_DATA)
    print(f"   • Average 91-94% of customers visit only once")
    print(f"   • Only 6-9% become repeat customers (2x+)")
    print(f"   • Huge opportunity: Converting even 5% more 1x → 2x could increase revenue by 10-15%")
    print()

    print("3. HIGH-VALUE REPEAT CUSTOMERS:")
    # Calculate average spending per visit for repeat customers
    for org_code, data in stores[:3]:  # Top 3 stores
        avg_2x = data['amount_2x'] / data['consumers_2x'] if data['consumers_2x'] > 0 else 0
        avg_1x = data['amount_1x'] / data['consumers_1x'] if data['consumers_1x'] > 0 else 0
        print(f"   • {data['store_name']}: 2x customers spend ¥{avg_2x:,.0f} vs 1x ¥{avg_1x:,.0f} (per customer)")
    print()

    print("4. REVENUE CONCENTRATION:")
    for org_code, data in stores[:1]:  # Top store
        repeat_revenue = data['amount_2x'] + data['amount_3x'] + data['amount_4x']
        repeat_pct = repeat_revenue / data['total_consumption'] * 100
        print(f"   • Top store: {data['repurchase_consumption_ratio']:.1f}% of revenue from repeat customers")
        print(f"   • Bottom store: {stores[-1][1]['repurchase_consumption_ratio']:.1f}% of revenue from repeat customers")
        print(f"   • Repeat customers are 2-3x more valuable per person")
    print()

    print("5. ACTIONABLE RECOMMENDATIONS:")
    print("   A. IMMEDIATE ACTIONS (0-30 days):")
    print("      • Launch post-visit survey for 1x customers to understand why they don't return")
    print("      • Implement 'second visit discount' (e.g., 20% off within 30 days)")
    print("      • Send personalized SMS/WeChat to 1x customers after 7 days")
    print()
    print("   B. SHORT-TERM INITIATIVES (1-3 months):")
    print("      • Create tiered membership program (Bronze → Silver → Gold)")
    print("      • Offer 'bring a friend' incentives for 2x customers")
    print("      • Analyze what top stores (MD00011, MD00009) do differently")
    print("      • Focus improvement efforts on bottom 2 stores (MD00006, MD00007)")
    print()
    print("   C. LONG-TERM STRATEGY (3-12 months):")
    print("      • Build predictive model to identify 'at-risk' 1x customers")
    print("      • Implement automated retention campaigns")
    print("      • Create exclusive menu items for repeat customers")
    print("      • Establish VIP program for 4x+ customers (currently only 0.3-0.5% of base)")
    print()

    print("6. FINANCIAL IMPACT PROJECTION:")
    print("   If we improve repurchase rate from 7.3% to 10% (2.7pp increase):")
    current_repeat_revenue = sum(d['amount_2x'] + d['amount_3x'] + d['amount_4x'] for d in REPURCHASE_DATA.values())
    projected_increase = current_repeat_revenue * 0.37  # 37% increase in repeat customers
    print(f"      • Current repeat customer revenue: ¥{current_repeat_revenue:,.0f}")
    print(f"      • Projected additional revenue: ¥{projected_increase:,.0f}")
    print(f"      • Annual impact: ¥{projected_increase * (365/381):,.0f}")
    print()

if __name__ == '__main__':
    main()
