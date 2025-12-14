"""
Configuration constants for Meituan Merchant Backend Crawler
"""

# Browser connection
CDP_URL = "http://localhost:9222"

# Database
DB_PATH = "data/meituan.db"

# Logging
LOG_DIR = "logs"

# Timeouts (in milliseconds)
DEFAULT_TIMEOUT = 30000
NAVIGATION_TIMEOUT = 60000

# Meituan URLs
MEITUAN_LOGIN_URL = "https://eepassport.meituan.com/portal/login"
MEITUAN_STORE_SELECTION_URL = "https://pos.meituan.com/web/rms-account#/selectorg"
MEITUAN_DASHBOARD_URL = "https://pos.meituan.com/web/marketing/home"
MEITUAN_MEMBERSHIP_REPORT_URL = "https://pos.meituan.com/web/marketing/crm/report/dpaas-summary-payment"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
