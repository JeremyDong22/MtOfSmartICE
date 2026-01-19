# Crawler Fix Summary - 2026-01-12

## Problem
The crawler has been failing every day since deployment due to a hardcoded macOS path in the CDP launcher.

## Root Cause
`src/browser/cdp_launcher.py:26` had a hardcoded path:
```python
DEFAULT_PROFILE_DIR = "/Users/jeremydong/Desktop/Smartice/APPs/MtOfSmartICE/data/chrome-profile"
```

This caused `PermissionError` on Linux when the cron job tried to create the directory.

## Missing Data
The following dates were missing:
- 2025-12-29, 2025-12-30
- 2026-01-03, 2026-01-06
- 2026-01-08, 2026-01-09, 2026-01-10, 2026-01-11

## Fixes Applied

### 1. Fixed CDP Launcher Path (src/browser/cdp_launcher.py:26)
Changed to use relative path:
```python
DEFAULT_PROFILE_DIR = str(Path(__file__).parent.parent.parent / "data" / "chrome-profile")
```

### 2. Backfilled Missing Data
Ran `scripts/backfill_missing_dates.sh` to crawl all 8 missing dates.
- All dates successfully crawled
- Both reports (equity_package_sales and business_summary) completed
- Data saved to both SQLite and Supabase

### 3. Updated Cron Job
Changed from:
```bash
0 0 * * * cd /home/smartice002/smartice/MtOfSmartICE && ./venv/bin/python src/main.py --report all >> /tmp/meituan-crawler.log 2>&1
```

To:
```bash
0 0 * * * cd /home/smartice002/smartice/MtOfSmartICE && START=$(date -d "3 days ago" +\%Y-\%m-\%d) && END=$(date -d "yesterday" +\%Y-\%m-\%d) && ./venv/bin/python src/main.py --report all --date "$START" --end-date "$END" >> /tmp/meituan-crawler.log 2>&1
```

This now crawls 3 days back to yesterday (e.g., if today is Jan 12, it crawls Jan 9-11).

## Verification
All dates from 2025-12-25 onwards are now present in the database with no gaps.

## Known Issue
One store is not mapped in Supabase:
- MD00013 - 宁桂杏山野烤肉（常熟四丈湾店）

This store's data is saved to SQLite but skipped in Supabase uploads. Add the mapping to `master_restaurant` table if needed.

## Next Steps
- Monitor `/tmp/meituan-crawler.log` to ensure cron runs successfully tonight
- Add missing store mapping to Supabase if needed
- Consider setting up alerts for crawler failures
