#!/bin/bash
# Setup cron job for Meituan crawler
# v1.3 - Match installed cron job: runs at 01:00, crawls 3-day range for reliability
# v1.2 - Added --report all to run all crawlers (equity_package_sales, business_summary, dish_sales)
# v1.1 - Linux version: uses venv instead of uv, runs at midnight daily
#        Default crawls 3 days for reliability (in case of missed runs)

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

CRON_JOB="0 1 * * * cd $PROJECT_DIR && START=\$(date -d \"3 days ago\" +\\%Y-\\%m-\\%d) && END=\$(date -d \"yesterday\" +\\%Y-\\%m-\\%d) && ./venv/bin/python src/main.py --report all --date \"\$START\" --end-date \"\$END\" >> /tmp/meituan-crawler.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "MtOfSmartICE"; then
    echo "Cron job already exists:"
    crontab -l | grep "MtOfSmartICE"
    echo ""
    read -p "Replace it? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Cancelled."
        exit 0
    fi
    # Remove old job
    crontab -l | grep -v "MtOfSmartICE" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job added:"
echo "$CRON_JOB"
echo ""
echo "Verify with: crontab -l"
