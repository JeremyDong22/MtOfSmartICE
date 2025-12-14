# Meituan Merchant Backend Crawler

Automated daily crawler for Meituan merchant backend membership card transaction data.

## Features

- 🔌 **CDP-only connection** - Connects to existing Chrome, no browser launching
- 🏪 **Multi-store support** - Automatically discovers and processes all stores
- 📊 **Daily automation** - Crawls yesterday's data automatically
- 🗄️ **SQLite database** - Stores data with full store_id + store_name tracking
- 🔄 **Extensible architecture** - Easy to add new crawlers for other reports
- 📝 **Comprehensive logging** - Daily log files with detailed tracking
- ⚡ **Error handling** - Retry logic, popup dismissal, graceful failures

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Chrome with Remote Debugging
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```

### 3. Login to Meituan
Open the Chrome browser and login at https://pos.meituan.com

### 4. Run the Crawler
```bash
# Crawl yesterday's data for all stores
python src/main.py

# Crawl specific date
python src/main.py --date 2025-12-13

# Crawl single store
python src/main.py --store 58188193
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
│              (Daily Crawler Entry Point)                     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├─► CDPSession (browser/cdp_session.py)
               │   └─ Connect to Chrome via CDP
               │
               ├─► StoreNavigator (browser/store_navigator.py)
               │   ├─ Navigate to dashboard
               │   ├─ Get all stores from dropdown
               │   └─ Switch between stores
               │
               ├─► MembershipCrawler (crawlers/membership_crawler.py)
               │   ├─ Inherits from BaseCrawler
               │   ├─ Navigate to report page
               │   ├─ Set date filter
               │   ├─ Select card type filters
               │   ├─ Extract summary data
               │   └─ Extract order details
               │
               └─► DatabaseManager (database/db_manager.py)
                   ├─ Save membership data
                   ├─ Log crawl status
                   └─ Export reports
```

## Directory Structure

```
src/
├── main.py                      # Daily crawler entry point
├── config.py                    # Centralized configuration
├── browser/
│   ├── cdp_session.py           # CDP-only browser connection
│   └── store_navigator.py       # Store discovery & switching
├── crawlers/
│   ├── base_crawler.py          # Abstract base class
│   └── membership_crawler.py    # Membership card crawler
└── utils/
    ├── date_utils.py            # Date handling utilities
    └── selectors.py             # CSS selectors

database/
└── db_manager.py                # Database operations

data/
└── meituan.db                   # SQLite database

logs/
└── crawler_YYYYMMDD.log         # Daily log files
```

## Usage

### Command-Line Arguments

```bash
python src/main.py [options]

Options:
  --cdp URL         CDP endpoint URL (default: http://localhost:9222)
  --date YYYY-MM-DD Target date (default: yesterday)
  --store XXXXXXXX  Crawl specific store only
  --force           Force re-crawl (ignore existing data)
```

### Examples

**Daily automated crawl**:
```bash
python src/main.py
```

**Crawl specific date**:
```bash
python src/main.py --date 2025-12-13
```

**Crawl single store**:
```bash
python src/main.py --store 58188193
```

**Force re-crawl**:
```bash
python src/main.py --force --date 2025-12-13
```

## Database Schema

### stores
Stores merchant/store information:
- `merchant_id` (PRIMARY KEY)
- `store_name`
- `org_code`

### membership_card_data
Daily summary data:
- `merchant_id` + `date` (UNIQUE)
- `cards_opened`
- `total_amount`

### card_details
Individual transaction details:
- Linked to `membership_card_data`
- Order number, time, status, amounts
- Phone number, card number

### crawl_log
Crawl operation tracking:
- `merchant_id` + `crawler_type` + `date` (UNIQUE)
- `status` (success/failed/partial)
- `records_count`
- `error_message`

## Viewing Results

### Query Database
```bash
sqlite3 data/meituan.db

SELECT s.store_name, m.date, m.cards_opened, m.total_amount
FROM membership_card_data m
JOIN stores s ON m.merchant_id = s.merchant_id
ORDER BY m.date DESC
LIMIT 20;
```

### Export to CSV
```python
from database.db_manager import DatabaseManager

db = DatabaseManager()
db.export_to_csv("reports/data.csv", start_date="2025-12-01")
```

### Check Logs
```bash
tail -f logs/crawler_$(date +%Y%m%d).log
```

## Scheduling (Cron)

Run automatically at 2 AM daily:

```bash
crontab -e

# Add this line
0 2 * * * cd /path/to/MtOfSmartICE && /path/to/venv/bin/python src/main.py >> logs/cron.log 2>&1
```

**Note**: Ensure Chrome is running with CDP before cron job executes.

## Adding New Crawlers

1. Create new crawler class inheriting from `BaseCrawler`:
```python
from src.crawlers.base_crawler import BaseCrawler

class NewCrawler(BaseCrawler):
    async def crawl(self, store_id: str, store_name: str) -> Dict[str, Any]:
        # Implement crawling logic
        return self.create_result(True, store_id, store_name, data=data)
```

2. Update `main.py` to use the new crawler

3. Add database tables if needed

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed guide.

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide with examples
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture documentation
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Refactoring details and migration guide

## Troubleshooting

**CDP connection failed**:
```bash
# Check if Chrome is running
lsof -i :9222

# Start Chrome with CDP
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```

**No stores found**:
1. Open Chrome and navigate to https://pos.meituan.com/web/marketing/home
2. Verify store dropdown is visible in top-right
3. Re-run crawler

**Data already exists**:
```bash
# Use --force to re-crawl
python src/main.py --force
```

For more troubleshooting tips, see [QUICKSTART.md](QUICKSTART.md#troubleshooting).

## Requirements

- Python 3.8+
- Chrome/Chromium browser
- playwright
- sqlite3
- Valid Meituan merchant account

## License

Internal use only.

## Support

Check logs in `logs/` directory for detailed information about crawl operations.

---

**Version**: 2.0 (Refactored Architecture)
**Last Updated**: 2025-12-14
