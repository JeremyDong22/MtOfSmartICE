# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meituan Merchant Backend Crawler - automated daily crawler for Meituan merchant backend 权益包售卖汇总表 (Equity Package Sales). Uses CDP-only browser connection and 集团账号 (group account) for aggregated data across all stores.

## Common Commands

### Prerequisites
The crawler **automatically launches Chrome with CDP** if not already running. Just run `python src/main.py` and it will:
1. Check if Chrome CDP is available on port 9222
2. If not, launch a new Chrome instance with CDP
3. If newly launched, prompt you to login first

```bash
# First run - will launch Chrome and ask you to login
python src/main.py

# After logging in, run again to crawl
python src/main.py
```

### Run Crawler
```bash
# Daily crawl (yesterday's data, all stores via 集团 account)
python src/main.py

# Specific date
python src/main.py --date 2025-12-13

# Date range
python src/main.py --date 2025-12-09 --end-date 2025-12-15

# Force re-crawl (ignore existing data)
python src/main.py --force

# Skip navigation (for debugging, assumes page is already configured)
python src/main.py --skip-navigation

# Custom CDP endpoint
python src/main.py --cdp http://localhost:9223

# Skip Supabase upload (SQLite only)
python src/main.py --no-supabase
```

### Database Queries
```bash
sqlite3 data/meituan.db

# View recent equity package sales
SELECT org_code, store_name, date, package_name, quantity_sold, total_sales
FROM equity_package_sales
ORDER BY date DESC LIMIT 20;
```

### View Logs
```bash
tail -f logs/crawler_$(date +%Y%m%d).log
```

## Architecture

```
main.py
  ↓
  CDPLauncher (browser/cdp_launcher.py)
    └─ Ensure Chrome CDP is available (launch if needed)
  ↓
  CDPSession (browser/cdp_session.py)
    └─ Connect to Chrome via CDP endpoint
  ↓
  EquityPackageSalesCrawler (crawlers/权益包售卖汇总表.py)
    ├─ Inherits from BaseCrawler
    ├─ Select 集团 account from selectorg page
    ├─ Navigate to 营销中心 → 数据报表 → 权益包售卖汇总表
    ├─ Configure filters (门店/日期 checkboxes, date range)
    ├─ Extract all pages of data
    └─ Save to databases
  ↓
  DatabaseManager (database/db_manager.py)        ← Local SQLite
    └─ Save to SQLite (UPSERT with conditional update)
  ↓
  SupabaseManager (database/supabase_manager.py)  ← Cloud Supabase
    ├─ Map org_code → restaurant_id via master_restaurant
    ├─ Upload to Supabase (error isolation per record)
    └─ Unknown stores logged but don't block others
```

### Key Design Patterns

- **CDP-only connection**: No `browser.launch()` - connects to existing Chrome with `--remote-debugging-port=9222`
- **Group account (集团账号)**: Single crawl extracts data for all stores, no per-store switching needed
- **Abstract base class**: Crawlers inherit from `BaseCrawler` which provides popup dismissal, iframe handling, result formatting
- **Conditional duplicate handling**: Only updates existing records if new values are higher
- **Dual database storage**: SQLite (local backup) + Supabase (cloud sync)
- **Error isolation**: Supabase upload failures for one store don't block other stores

### Adding New Crawlers

1. Create class inheriting from `BaseCrawler` in `src/crawlers/`:
```python
from src.crawlers.base_crawler import BaseCrawler

class NewCrawler(BaseCrawler):
    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        # Navigate, extract, save
        return self.create_result(True, store_id or "GROUP", store_name or "集团", data=data)
```

2. Update `main.py` to instantiate and run the new crawler
3. Add database tables in `db_manager.py` if needed

## Configuration

All settings in `src/config.py`:
- `CDP_URL`: Chrome DevTools Protocol endpoint (default: `http://localhost:9222`)
- `DB_PATH`: Database path
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anon key (embedded, no env var needed)
- `MEITUAN_*_URL`: Target URLs
- `DEFAULT_TIMEOUT`: Timeout configuration

## Database Schema

详细 schema 和门店映射表见 [database/SCHEMA.md](database/SCHEMA.md)。

**快速参考**:
- **Local SQLite** (`database/meituan_data.db`): `mt_stores`, `mt_equity_package_sales`
- **Cloud Supabase**: `master_restaurant`, `mt_equity_package_sales`
- **映射关系**: org_code (美团) ↔ restaurant_id (Supabase)

## Important Notes

- Chrome CDP auto-launches if not running
- Login session must be valid in Chrome
- Uses 集团账号 to get aggregated data for all stores in one crawl
- Report iframe is `crm-smart` - crawler handles automatic iframe detection
- Conditional update: only overwrites existing records if new values are higher
- Supabase sync is automatic (use `--no-supabase` to skip)
- New stores need `meituan_org_code` mapping in `master_restaurant` table for Supabase upload
