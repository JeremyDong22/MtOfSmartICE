#!/bin/bash
# Check if last night's cron job ran successfully

echo "=== Checking Last Crawler Run ==="
echo ""

# Check cron log for today's run
TODAY=$(date +%Y-%m-%d)
echo "Looking for runs on $TODAY..."
echo ""

if grep -q "$TODAY" /tmp/meituan-crawler.log 2>/dev/null; then
    echo "✓ Cron log found for today"
    echo ""
    echo "Last run summary:"
    grep -A 10 "CRAWL SUMMARY" /tmp/meituan-crawler.log | tail -15
    echo ""

    # Check if it succeeded
    if grep -q "TOTAL: 2/2 reports succeeded" /tmp/meituan-crawler.log; then
        echo "✓ Both reports succeeded!"
    else
        echo "✗ Some reports failed. Check full log:"
        echo "  tail -100 /tmp/meituan-crawler.log"
    fi
else
    echo "✗ No cron run found for today"
    echo "Check cron status: crontab -l"
fi

echo ""
echo "=== Recent Data in Database ==="
python3 -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('database/meituan_data.db')
cursor = conn.cursor()

# Check last 3 days
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
cursor.execute('SELECT date, COUNT(*) FROM mt_equity_package_sales WHERE date >= ? GROUP BY date ORDER BY date DESC LIMIT 3', (yesterday,))
print('Equity Package Sales:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} records')
"
