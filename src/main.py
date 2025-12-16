"""
Daily Crawler - Main entry point for automated daily crawling
v2.4 - Default to 3-day range for cron reliability

This script:
1. Ensures Chrome CDP is available (launches if needed)
2. Connects to Chrome via CDP
3. Runs EquityPackageSalesCrawler for 集团 account (aggregated data for all stores)
4. Saves data to SQLite database (local)
5. Uploads to Supabase cloud (always enabled with anon key)
6. Prints summary

Supabase Robustness:
- Unknown stores are logged but don't block other records
- Error isolation: one failed record won't affect others
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.browser import CDPSession, ensure_cdp_available, get_cdp_url
from src.crawlers.权益包售卖汇总表 import EquityPackageSalesCrawler
from src.utils import get_yesterday, get_today, get_days_ago
from src.config import CDP_URL, LOG_DIR, SUPABASE_ENABLED
from src.browser.cdp_launcher import DEFAULT_CDP_PORT, DEFAULT_PROFILE_DIR, DEFAULT_STARTUP_URL
from database.db_manager import DatabaseManager
from database.supabase_manager import SupabaseManager

# Setup logging
log_file = Path(LOG_DIR) / f"crawler_{datetime.now().strftime('%Y%m%d')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """
    Main entry point - runs EquityPackageSalesCrawler (集团 aggregated).
    """
    args = parse_args()

    logger.info("=" * 80)
    logger.info("Meituan Merchant Backend Daily Crawler - Equity Package Sales")
    logger.info("=" * 80)

    # Determine target date range
    # Default: 3 days ago to yesterday (for cron reliability)
    target_date = args.date if args.date else get_days_ago(3)
    end_date = args.end_date if args.end_date else get_yesterday()
    logger.info(f"Date range: {target_date} to {end_date}")

    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager()

    # Ensure Chrome CDP is available (launch if needed)
    cdp_port = DEFAULT_CDP_PORT
    if args.cdp:
        # Extract port from custom CDP URL if provided
        cdp_url = args.cdp
        if ":" in cdp_url.split("//")[-1]:
            cdp_port = int(cdp_url.split(":")[-1])
    else:
        cdp_url = CDP_URL

    logger.info("Ensuring Chrome CDP is available...")
    cdp_success, was_launched = await ensure_cdp_available(
        port=cdp_port,
        profile_dir=DEFAULT_PROFILE_DIR,
        startup_url=DEFAULT_STARTUP_URL
    )

    if not cdp_success:
        logger.error("Failed to initialize Chrome CDP. Please start Chrome manually with:")
        logger.error(f"  ./scripts/start_chrome_cdp.sh")
        return

    if was_launched:
        logger.info("Launched new Chrome instance with CDP")
        logger.info("Please login to Meituan in the browser window, then run this script again.")
        return
    else:
        logger.info("Reusing existing Chrome CDP session")

    # Initialize CDP session
    logger.info(f"Connecting to Chrome via CDP: {cdp_url}")
    session = CDPSession(cdp_url)

    results = {
        "date_range": f"{target_date} to {end_date}",
        "success": False,
        "total_records": 0,
        "error": None,
        "start_time": datetime.now().isoformat()
    }

    try:
        # Connect to browser
        await session.connect()
        page = await session.get_page()
        logger.info(f"Connected to browser. Current URL: {page.url}")

        # Get iframe (will be re-acquired by crawler)
        frame = await get_report_frame(page)

        # Initialize crawler
        skip_nav = getattr(args, 'skip_navigation', False)
        crawler = EquityPackageSalesCrawler(
            page=page,
            frame=frame,
            db_manager=db,
            target_date=target_date,
            end_date=end_date,
            skip_navigation=skip_nav
        )

        # Run crawler
        logger.info("Running EquityPackageSalesCrawler for 集团 account...")
        result = await crawler.crawl()

        if result["success"]:
            logger.info("EquityPackageSalesCrawler completed successfully")
            record_count = result["data"].get("record_count", 0)
            save_stats = result["data"].get("save_stats", {})
            results["success"] = True
            results["total_records"] = record_count
            results["save_stats"] = save_stats

            # Print SQLite save statistics
            logger.info(
                f"SQLite: {save_stats.get('inserted', 0)} inserted, "
                f"{save_stats.get('updated', 0)} updated, "
                f"{save_stats.get('skipped', 0)} skipped"
            )

            # Upload to Supabase (always enabled unless --no-supabase flag)
            records = result["data"].get("records", [])
            skip_supabase = getattr(args, 'no_supabase', False)

            if records and not skip_supabase:
                logger.info("Uploading to Supabase...")
                supabase_stats = upload_to_supabase(records)
                results["supabase_stats"] = supabase_stats

                # Log Supabase results
                logger.info(
                    f"Supabase: {supabase_stats.get('inserted', 0)} inserted, "
                    f"{supabase_stats.get('updated', 0)} updated, "
                    f"{supabase_stats.get('skipped', 0)} skipped, "
                    f"{supabase_stats.get('failed', 0)} failed"
                )

                # Warn about unknown stores
                unknown_stores = supabase_stats.get('unknown_stores', [])
                if unknown_stores:
                    logger.warning(
                        f"未知门店 ({len(unknown_stores)}个): "
                        f"{[s['org_code'] for s in unknown_stores]}"
                    )
                    logger.warning(
                        "请在 master_restaurant 表中添加 meituan_org_code 映射"
                    )
            elif skip_supabase:
                logger.info("Supabase upload skipped (--no-supabase flag)")

            # Print sample data for verification
            if records:
                logger.info(f"Sample records (first 3):")
                for rec in records[:3]:
                    logger.info(f"  {rec.get('org_code')} | {rec.get('store_name')} | {rec.get('date')} | "
                               f"{rec.get('package_name')} | {rec.get('quantity_sold')} sold | ¥{rec.get('total_sales')}")
        else:
            logger.error(f"EquityPackageSalesCrawler failed: {result.get('error')}")
            results["error"] = result.get("error", "Unknown error")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        results["error"] = str(e)

    finally:
        # Cleanup
        logger.info("Closing browser connection...")
        await session.close()

        # Print summary
        results["end_time"] = datetime.now().isoformat()
        print_summary(results)


async def get_report_frame(page):
    """
    Get the report iframe (crm-smart) or return main page.

    Args:
        page: Playwright page object

    Returns:
        Frame or page object
    """
    main_url = page.url
    for frame in page.frames:
        if frame.url == main_url:
            continue
        if 'crm-smart' in frame.url:
            logger.info(f"Found crm-smart iframe: {frame.url}")
            return frame

    logger.info("No crm-smart iframe found, using main page")
    return page


def upload_to_supabase(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Upload crawled records to Supabase with robust error handling.

    This function implements error isolation - each record is processed independently.
    If one store is unknown (e.g., MD00012 not mapped), other stores continue normally.

    Args:
        records: List of crawled records with org_code, store_name, date, etc.

    Returns:
        Stats dictionary with inserted, updated, skipped, failed counts
        and list of unknown_stores
    """
    try:
        # Initialize Supabase manager (will use cached connection if available)
        supabase_mgr = SupabaseManager()

        # Save records - this handles error isolation internally
        stats = supabase_mgr.save_equity_package_sales(records)

        return stats

    except Exception as e:
        logger.error(f"Supabase upload error: {e}")
        return {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": len(records),
            "unknown_stores": [],
            "error": str(e)
        }


def print_summary(results: Dict[str, Any]) -> None:
    """
    Print crawl summary.

    Args:
        results: Results dictionary
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("CRAWL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Date range: {results['date_range']}")
    logger.info(f"Status: {'SUCCESS' if results['success'] else 'FAILED'}")
    logger.info(f"Total records extracted: {results['total_records']}")

    # Display SQLite save statistics
    save_stats = results.get('save_stats', {})
    if save_stats:
        logger.info(f"SQLite Database:")
        logger.info(f"  - Inserted (new): {save_stats.get('inserted', 0)}")
        logger.info(f"  - Updated (higher values): {save_stats.get('updated', 0)}")
        logger.info(f"  - Skipped (existing data not lower): {save_stats.get('skipped', 0)}")

    # Display Supabase statistics if available
    supabase_stats = results.get('supabase_stats', {})
    if supabase_stats:
        logger.info(f"Supabase Cloud:")
        logger.info(f"  - Inserted: {supabase_stats.get('inserted', 0)}")
        logger.info(f"  - Updated: {supabase_stats.get('updated', 0)}")
        logger.info(f"  - Skipped: {supabase_stats.get('skipped', 0)}")
        logger.info(f"  - Failed: {supabase_stats.get('failed', 0)}")

        # Report unknown stores
        unknown_stores = supabase_stats.get('unknown_stores', [])
        if unknown_stores:
            logger.info(f"  - Unknown stores (need mapping): {len(unknown_stores)}")
            for store in unknown_stores[:5]:  # Show first 5
                logger.info(f"      {store['org_code']}: {store['store_name']}")
            if len(unknown_stores) > 5:
                logger.info(f"      ... and {len(unknown_stores) - 5} more")

    if results['error']:
        logger.info(f"Error: {results['error']}")

    logger.info("=" * 80)
    logger.info(f"Start time: {results['start_time']}")
    logger.info(f"End time: {results['end_time']}")
    logger.info("=" * 80)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Meituan Merchant Backend Daily Crawler - Equity Package Sales',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run daily crawl for yesterday's data
  python src/main.py

  # Run for specific date
  python src/main.py --date 2025-12-13

  # Run for date range
  python src/main.py --date 2025-12-09 --end-date 2025-12-15

  # Use custom CDP URL
  python src/main.py --cdp http://localhost:9223

  # Force re-crawl (ignore existing data)
  python src/main.py --force

  # Skip navigation (for debugging, assumes page is already configured)
  python src/main.py --skip-navigation

  # Skip Supabase upload (SQLite only)
  python src/main.py --no-supabase

Note: Supabase upload is enabled by default using anon key.
        """
    )

    parser.add_argument(
        '--cdp',
        type=str,
        default=None,
        help=f'CDP endpoint URL (default: {CDP_URL})'
    )

    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Target/start date in YYYY-MM-DD format (default: 3 days ago)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date for date range (default: yesterday)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-crawl even if data exists'
    )

    parser.add_argument(
        '--skip-navigation',
        action='store_true',
        help='Skip page navigation and use current page state (for debugging)'
    )

    parser.add_argument(
        '--no-supabase',
        action='store_true',
        help='Skip Supabase upload, save to SQLite only'
    )

    return parser.parse_args()


if __name__ == '__main__':
    asyncio.run(main())
