# Quick Start Guide

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Chrome with Remote Debugging
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```

### 3. Login to Meituan
1. Open Chrome browser (from step 2)
2. Navigate to https://pos.meituan.com
3. Login with your credentials
4. Verify you can access the dashboard

## Running the Crawler

### Basic Usage

**Run daily crawl for yesterday's data**:
```bash
python src/main.py
```

This will:
- Connect to Chrome via CDP
- Discover all stores
- Crawl yesterday's membership card data for each store
- Save to `data/meituan.db`

### Advanced Usage

**Crawl specific date**:
```bash
python src/main.py --date 2025-12-13
```

**Crawl single store**:
```bash
python src/main.py --store 58188193
```

**Force re-crawl (override existing data)**:
```bash
python src/main.py --force
```

**Custom CDP endpoint**:
```bash
python src/main.py --cdp http://localhost:9223
```

## Viewing Results

### Check Database
```bash
sqlite3 data/meituan.db

-- View recent data
SELECT s.store_name, m.date, m.cards_opened, m.total_amount
FROM membership_card_data m
JOIN stores s ON m.merchant_id = s.merchant_id
ORDER BY m.date DESC, s.store_name
LIMIT 20;

-- View crawl status
SELECT s.store_name, c.date, c.status, c.records_count
FROM crawl_log c
JOIN stores s ON c.merchant_id = s.merchant_id
ORDER BY c.crawled_at DESC
LIMIT 20;
```

### Export to CSV
```python
from database.db_manager import DatabaseManager

db = DatabaseManager()
db.export_to_csv("reports/data.csv", start_date="2025-12-01", end_date="2025-12-14")
```

## Logs

Logs are in `logs/crawler_YYYYMMDD.log`:
```bash
# View today's log
tail -f logs/crawler_$(date +%Y%m%d).log

# Search for errors
grep ERROR logs/crawler_*.log
```

## Scheduling (Cron)

Run automatically every night at 2 AM:

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths as needed)
0 2 * * * cd /home/smartice002/smartice/MtOfSmartICE && /path/to/venv/bin/python src/main.py >> logs/cron.log 2>&1
```

**Note**: Ensure Chrome is already running with CDP enabled before cron job runs.

## Troubleshooting

### CDP Connection Failed
```bash
# Check if Chrome is running with CDP
lsof -i :9222

# If not, start Chrome:
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
```

### No Stores Found
1. Open Chrome browser
2. Navigate to https://pos.meituan.com/web/marketing/home
3. Verify you can see store dropdown in top-right
4. Try running crawler again

### Data Already Exists
If you want to re-crawl:
```bash
python src/main.py --force
```

## Project Structure

```
src/
├── main.py              # Run this to start crawler
├── config.py            # Configuration settings
├── browser/
│   ├── cdp_session.py   # Chrome connection
│   └── store_navigator.py  # Store switching
├── crawlers/
│   ├── base_crawler.py     # Base class
│   └── membership_crawler.py  # Membership data
└── utils/
    ├── date_utils.py    # Date utilities
    └── selectors.py     # CSS selectors

database/
└── db_manager.py        # Database operations

data/
└── meituan.db          # SQLite database

logs/
└── crawler_YYYYMMDD.log  # Daily logs
```

## Next Steps

1. **Review Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation
2. **Add New Crawlers**: Follow the guide in ARCHITECTURE.md
3. **Customize Configuration**: Edit `src/config.py`
4. **Set Up Monitoring**: Add alerts for failed crawls

## Support

For issues or questions, check:
- Logs in `logs/` directory
- Database crawl_log table for status
- [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation
