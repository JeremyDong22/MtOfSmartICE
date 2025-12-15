"""
Configuration constants for Meituan Merchant Backend Crawler
v1.3 - Load Supabase credentials from .env file
"""

import os
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, use system env vars

# Browser connection
CDP_URL = "http://localhost:9222"

# Local Database (SQLite)
DB_PATH = "data/meituan.db"

# Supabase Configuration
# Credentials loaded from .env file or environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_ENABLED = bool(SUPABASE_KEY)  # Enable if key is set

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
