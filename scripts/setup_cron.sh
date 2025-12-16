#!/bin/bash
# Setup cron job for Meituan crawler
# v1.0 - Auto-detects project path, adds daily midnight cron task

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

CRON_JOB="0 0 * * * cd $PROJECT_DIR && uv run python src/main.py >> /tmp/meituan-crawler.log 2>&1"

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
