# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meituan Merchant Backend Crawler - automated daily crawler for Meituan merchant backend membership card transaction data. Uses CDP-only browser connection (connects to existing Chrome, no browser launching).

## Common Commands

### Prerequisites (Run Chrome First)
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```
Then manually login to https://pos.meituan.com in the Chrome window.

### Run Crawler
```bash
# Daily crawl (yesterday's data, all stores)
python src/main.py

# Specific date
python src/main.py --date 2025-12-13

# Single store
python src/main.py --store 58188193

# Force re-crawl (ignore existing data)
python src/main.py --force

# Custom CDP endpoint
python src/main.py --cdp http://localhost:9223
```

### Database Queries
```bash
sqlite3 data/meituan.db

# View recent data
SELECT s.store_name, m.date, m.cards_opened, m.total_amount
FROM membership_card_data m
JOIN stores s ON m.merchant_id = s.merchant_id
ORDER BY m.date DESC LIMIT 20;
```

### View Logs
```bash
tail -f logs/crawler_$(date +%Y%m%d).log
```

## Architecture

```
main.py
  ↓
  CDPSession (browser/cdp_session.py)
    └─ Connect to Chrome via CDP endpoint
  ↓
  StoreNavigator (browser/store_navigator.py)
    ├─ Navigate to dashboard
    ├─ Get all stores from dropdown
    └─ Switch between stores
  ↓
  MembershipCrawler (crawlers/membership_crawler.py)
    ├─ Inherits from BaseCrawler
    ├─ Navigate to report page
    ├─ Set date filter
    ├─ Select card type filters
    ├─ Extract summary data
    └─ Extract order details
  ↓
  DatabaseManager (database/db_manager.py)
    ├─ Save membership data (UPSERT)
    ├─ Log crawl status
    └─ Export reports
```

### Key Design Patterns

- **CDP-only connection**: No `browser.launch()` - connects to existing Chrome with `--remote-debugging-port=9222`
- **Abstract base class**: All crawlers inherit from `BaseCrawler` which provides date handling, popup dismissal, retry logic
- **Store-aware data**: All tables store both `store_id` AND `store_name` together
- **Crawl tracking**: `crawl_log` table tracks crawl status per store/date/type with `UNIQUE(merchant_id, crawler_type, date)`

### Adding New Crawlers

1. Create class inheriting from `BaseCrawler` in `src/crawlers/`:
```python
from src.crawlers.base_crawler import BaseCrawler

class NewCrawler(BaseCrawler):
    async def crawl(self, store_id: str, store_name: str) -> Dict[str, Any]:
        # Navigate, extract, save
        return self.create_result(True, store_id, store_name, data=data)
```

2. Update `main.py` to instantiate and run the new crawler
3. Add database tables in `db_manager.py` if needed

## Configuration

All settings in `src/config.py`:
- `CDP_URL`: Chrome DevTools Protocol endpoint (default: `http://localhost:9222`)
- `DB_PATH`: Database path
- `MEITUAN_*_URL`: Target URLs
- `DEFAULT_TIMEOUT`, `MAX_RETRIES`, `RETRY_DELAY`: Timing configuration

## Database Schema

- **stores**: merchant_id (PK), store_name, org_code
- **membership_card_data**: merchant_id + date (UNIQUE), cards_opened, total_amount
- **card_details**: Linked to membership_card_data via foreign key
- **crawl_log**: merchant_id + crawler_type + date (UNIQUE), status, records_count, error_message

## Important Notes

- Chrome must be running with CDP before running crawler
- Login session must be valid in Chrome
- Store dropdown is in top-right header showing "商户号: XXXXXXXX"
- Report iframe is `crm-smart` - crawler handles automatic iframe detection
- Uses `--force` sparingly to avoid duplicate data processing
