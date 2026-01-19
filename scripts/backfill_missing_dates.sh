#!/bin/bash
# Backfill missing dates for the crawler
# Run this after logging into Chrome CDP

cd "$(dirname "$0")/.."

# Missing dates to backfill
DATES=(
    "2025-12-29"
    "2025-12-30"
    "2026-01-03"
    "2026-01-06"
    "2026-01-08"
    "2026-01-09"
    "2026-01-10"
    "2026-01-11"
)

echo "Starting backfill for ${#DATES[@]} missing dates..."
echo "Make sure you're logged into 美团管家 in Chrome CDP first!"
echo ""

for date in "${DATES[@]}"; do
    echo "=========================================="
    echo "Crawling date: $date"
    echo "=========================================="
    ./venv/bin/python src/main.py --report all --date "$date"

    if [ $? -eq 0 ]; then
        echo "✓ Successfully crawled $date"
    else
        echo "✗ Failed to crawl $date"
    fi

    # Small delay between dates to avoid rate limiting
    sleep 2
done

echo ""
echo "Backfill complete!"
