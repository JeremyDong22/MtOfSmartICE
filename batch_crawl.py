"""
Batch Crawler - Crawl multiple dates for all stores

Usage:
    python batch_crawl.py --start 2025-11-14 --end 2025-12-14
"""

import asyncio
import argparse
import subprocess
import sys
from datetime import datetime, timedelta


def daterange(start_date: str, end_date: str):
    """Generate dates from start to end (inclusive)."""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    current = start
    while current <= end:
        yield current.strftime('%Y-%m-%d')
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description='Batch crawl multiple dates')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--cdp', type=str, default='http://localhost:9222', help='CDP URL')
    args = parser.parse_args()

    dates = list(daterange(args.start, args.end))
    total_dates = len(dates)

    print("=" * 70)
    print(f"批量爬取: {args.start} 到 {args.end}")
    print(f"共 {total_dates} 天")
    print("=" * 70)

    for i, date in enumerate(dates, 1):
        print(f"\n[{i}/{total_dates}] 正在爬取 {date}...")
        print("-" * 50)

        # Run the crawler for this date
        cmd = [
            sys.executable, 'src/main.py',
            '--date', date,
            '--cdp', args.cdp
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                timeout=600  # 10 minutes per date
            )

            if result.returncode == 0:
                print(f"✓ {date} 完成")
            else:
                print(f"✗ {date} 失败 (exit code: {result.returncode})")

        except subprocess.TimeoutExpired:
            print(f"✗ {date} 超时")
        except Exception as e:
            print(f"✗ {date} 错误: {e}")

    print("\n" + "=" * 70)
    print("批量爬取完成!")
    print("=" * 70)


if __name__ == '__main__':
    main()
