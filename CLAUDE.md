# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Site Merchant Backend Crawler - automated daily crawler for:
- **美团管家** (pos.meituan.com):
  - 权益包售卖汇总表 (equity_package_sales) - Package sales by store/date
  - 综合营业统计 (business_summary) - Revenue, orders, payment composition
- **大众点评** (e.dianping.com): [skeleton ready, crawlers pending]

Uses CDP-only browser connection and 集团账号 (group account) for aggregated data across all stores.

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
# 美团管家 - 权益包售卖汇总表 (default)
python src/main.py

# 美团管家 - 综合营业统计
python src/main.py --report business_summary

# Run ALL crawlers sequentially (recommended for cron)
python src/main.py --report all

# Run specific crawlers sequentially
python src/main.py --report equity_package_sales business_summary

# Specific date (default: yesterday)
python src/main.py --date 2025-12-13

# Date range (3 days back)
python src/main.py --date 2025-12-09 --end-date 2025-12-15

# Force re-crawl (update existing records even if values unchanged)
python src/main.py --force

# Skip navigation (for debugging, assumes page is already configured)
python src/main.py --skip-navigation

# Custom CDP endpoint
python src/main.py --cdp http://localhost:9223

# Skip Supabase upload (SQLite only)
python src/main.py --no-supabase
```

### Default Values
- `--site`: guanjia (美团管家)
- `--report`: equity_package_sales (权益包售卖汇总表)
- `--date`: yesterday (calculated at runtime)
- `--end-date`: same as start date (single day)

### Database Queries
```bash
sqlite3 database/meituan_data.db

# View recent equity package sales
SELECT org_code, date, package_name, quantity_sold, total_sales
FROM mt_equity_package_sales
ORDER BY date DESC LIMIT 20;
```

### View Logs
```bash
tail -f logs/crawler_$(date +%Y%m%d).log
```

### Linux Deployment (Cron)

**Run all crawlers daily at midnight, crawling 3 days back until yesterday:**

```bash
# Manual cron setup - add to crontab -e
# Runs at 00:00 daily, crawls 3 days back (e.g., Dec 15-17 if today is Dec 18)
# Uses --report all to run both equity_package_sales and business_summary sequentially

0 0 * * * cd /path/to/MtOfSmartICE && START=$(date -d "3 days ago" +\%Y-\%m-\%d) && END=$(date -d "yesterday" +\%Y-\%m-\%d) && python src/main.py --report all --date $START --end-date $END >> /tmp/meituan-crawler.log 2>&1
```

**Or use the setup script:**
```bash
# Auto-setup cron job
./scripts/setup_cron.sh

# Verify cron is set
crontab -l

# View cron logs
tail -f /tmp/meituan-crawler.log
```

**Important for cron:**
- Chrome must be running with CDP enabled (port 9222)
- User must be logged into 美团管家 in the Chrome session
- Consider running Chrome in a tmux/screen session for persistence

## Architecture

Three-layer architecture separating browser connection, site navigation, and data extraction:

```
src/
├── main.py                           # Unified entry point (--site, --report)
│
├── browser/                          # Layer 1: Browser Connection
│   ├── cdp_launcher.py               # CDP detect + launch Chrome
│   └── cdp_session.py                # CDP session management
│
├── sites/                            # Layer 2: Site Navigation
│   ├── base_site.py                  # Abstract base class
│   ├── meituan_guanjia.py            # 美团管家 (pos.meituan.com)
│   └── dianping.py                   # 大众点评 (e.dianping.com)
│
├── crawlers/                         # Layer 3: Data Extraction
│   ├── base_crawler.py               # Abstract base class
│   ├── guanjia/                      # 美团管家 crawlers
│   │   ├── equity_package_sales.py   # 权益包售卖汇总表
│   │   └── business_summary.py       # 综合营业统计
│   └── dianping/                     # 大众点评 crawlers
│       └── (pending)
│
└── database/
    ├── db_manager.py                 # Local SQLite
    └── supabase_manager.py           # Cloud Supabase
```

### Data Flow

```
main.py
  ↓
  CDPLauncher (browser/cdp_launcher.py)
    └─ Ensure Chrome CDP is available (launch if needed)
  ↓
  CDPSession (browser/cdp_session.py)
    └─ Connect to Chrome via CDP endpoint
  ↓
  Site (sites/meituan_guanjia.py or sites/dianping.py)
    ├─ Login detection
    ├─ Account selection (集团账号)
    └─ Navigate to report page
  ↓
  Crawler (crawlers/guanjia/equity_package_sales.py)
    ├─ Configure filters (checkboxes, date range)
    ├─ Extract all pages of data
    └─ Save to databases
  ↓
  DatabaseManager → SQLite (local)
  SupabaseManager → Supabase (cloud)
```

### Key Design Patterns

- **Three-layer separation**: Browser → Sites → Crawlers (easy to add new sites)
- **CDP-only connection**: No `browser.launch()` - connects to existing Chrome with `--remote-debugging-port=9222`
- **Group account (集团账号)**: Single crawl extracts data for all stores
- **Abstract base classes**: `BaseSite` and `BaseCrawler` provide common functionality
- **Conditional duplicate handling**: Only updates existing records if new values are higher
- **Dual database storage**: SQLite (local backup) + Supabase (cloud sync)
- **Error isolation**: Supabase upload failures for one store don't block other stores

### Adding New Sites

1. Create site class in `src/sites/`:
```python
from src.sites.base_site import BaseSite

class NewSite(BaseSite):
    SITE_NAME = "新网站"
    BASE_URL = "https://example.com"

    async def is_logged_in(self) -> bool:
        # Check login status
        pass

    async def navigate_to_report(self, report_name: str) -> bool:
        # Navigate to specific report page
        pass
```

2. Register in `src/main.py` SITES dict:
```python
SITES = {
    "newsite": {
        "class": NewSite,
        "name": "新网站",
        "startup_url": "https://example.com",
        "reports": {
            "report_name": NewCrawler
        }
    }
}
```

### Adding New Crawlers

1. Create crawler class in `src/crawlers/{site_name}/`:
```python
from src.crawlers.base_crawler import BaseCrawler

class NewCrawler(BaseCrawler):
    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        # Configure filters, extract data, save
        return self.create_result(True, store_id or "GROUP", store_name or "集团", data=data)
```

2. Register in site's REPORTS dict and `main.py` SITES

3. Add database tables in `db_manager.py` if needed

## Configuration

All settings in `src/config.py`:
- `CDP_URL`: Chrome DevTools Protocol endpoint (default: `http://localhost:9222`)
- `DB_PATH`: Database path
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anon key
- `DEFAULT_TIMEOUT`: Timeout configuration

## Database Schema

详细 schema 和门店映射表见 [database/SCHEMA.md](database/SCHEMA.md)。

**快速参考**:
- **Local SQLite** (`database/meituan_data.db`):
  - `mt_stores` - Store info
  - `mt_equity_package_sales` - Package sales data
  - `mt_business_summary` - Daily revenue/composition data (JSON for nested columns)
- **Cloud Supabase**:
  - `master_restaurant` - Store master data with mappings
  - `mt_equity_package_sales` - Package sales
  - `mt_business_summary` - Business summary with composition_data JSON
- **映射关系**: org_code (美团) ↔ restaurant_id (Supabase)

## Important Notes

- Chrome CDP auto-launches if not running
- Login session must be valid in Chrome
- Uses 集团账号 to get aggregated data for all stores in one crawl
- Report iframe is `crm-smart` - crawler handles automatic iframe detection
- Conditional update: only overwrites existing records if new values are higher
- Supabase sync is automatic (use `--no-supabase` to skip)
- New stores need `meituan_org_code` mapping in `master_restaurant` table for Supabase upload
