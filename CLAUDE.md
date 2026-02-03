# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Site Merchant Backend Crawler - automated daily crawler for:
- **美团管家** (pos.meituan.com):
  - 权益包售卖汇总表 (equity_package_sales) - Package sales by store/date
  - 综合营业统计 (business_summary) - Revenue, orders, payment composition
  - 菜品综合统计 (dish_sales) - Dish-level sales, returns, gifts statistics
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

# 美团管家 - 菜品综合统计
python src/main.py --report dish_sales

# Run ALL crawlers sequentially (recommended for cron)
python src/main.py --report all

# Run specific crawlers sequentially
python src/main.py --report equity_package_sales business_summary dish_sales

# Specific date (default: yesterday)
python src/main.py --date 2025-12-13

# Date range (equity_package_sales and business_summary support ranges)
python src/main.py --report equity_package_sales business_summary --date 2025-12-09 --end-date 2025-12-15

# CRITICAL: dish_sales does NOT support date ranges - it will FAIL with an error
# The crawler rejects date ranges to prevent data corruption from aggregation
# Run dish_sales for ONE day at a time:
python src/main.py --report dish_sales --date 2025-12-13

# For cron jobs, run all reports for a SINGLE day (recommended):
python src/main.py --report all --date $(date -d "yesterday" +%Y-%m-%d)

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

**IMPORTANT: Machine Restart Handling**

The crawler now uses a wrapper script (`run_crawler_with_cdp.sh`) that automatically handles machine restarts by:
1. Checking if Chrome CDP is running
2. Launching Chrome with CDP if needed
3. Waiting for CDP to be ready before running the crawler

This ensures the crawler works reliably even after system reboots.

**Setup (Recommended):**

```bash
# Auto-setup cron job with wrapper script
./scripts/setup_cron.sh

# Verify cron is set
crontab -l

# View cron logs
tail -f /tmp/meituan-crawler.log
```

**Manual cron setup:**

```bash
# Add to crontab -e
# Runs at 01:00 daily, crawls yesterday's data (single day)
# Uses wrapper script to ensure Chrome CDP is running
# IMPORTANT: Single day only - dish_sales does not support date ranges

0 1 * * * /path/to/MtOfSmartICE/scripts/run_crawler_with_cdp.sh --report all --date $(date -d "yesterday" +\%Y-\%m-\%d)
```

**Test after machine restart:**

```bash
# Run comprehensive test
./scripts/test_after_restart.sh

# Or manually test
./scripts/run_crawler_with_cdp.sh --report equity_package_sales --date $(date -d "yesterday" +%Y-%m-%d)
```

**Troubleshooting:**

If the crawler fails after a reboot:
1. Check if Chrome CDP is running: `curl http://localhost:9222/json/version`
2. Check cron logs: `tail -50 /tmp/meituan-crawler.log`
3. Run test script: `./scripts/test_after_restart.sh`
4. Manually launch Chrome: `google-chrome --remote-debugging-port=9222 --user-data-dir=./data/chrome-profile --no-first-run --no-default-browser-check https://pos.meituan.com &`


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
│   │   ├── business_summary.py       # 综合营业统计
│   │   └── dish_sales.py             # 菜品综合统计
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
  - `mt_dish_sales` - Dish-level sales statistics (30+ metrics)
- **Cloud Supabase**:
  - `master_restaurant` - Store master data with mappings
  - `mt_equity_package_sales` - Package sales
  - `mt_business_summary` - Business summary with composition_data JSON
  - `mt_dish_sales` - Dish sales with Chinese column names
- **映射关系**: org_code (美团) ↔ restaurant_id (Supabase)

## Important Notes

- Chrome CDP auto-launches if not running
- Login session must be valid in Chrome
- Uses 集团账号 to get aggregated data for all stores in one crawl
- Report iframe is `crm-smart` - crawler handles automatic iframe detection
- Conditional update: only overwrites existing records if new values are higher
- Supabase sync is automatic (use `--no-supabase` to skip)
- New stores need `meituan_org_code` mapping in `master_restaurant` table for Supabase upload
