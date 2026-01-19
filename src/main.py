# Daily Crawler - Unified entry point for multi-site crawling
# v3.5 - Enhanced retry logic to retry at least once for any error
#   - All errors now get at least 1 retry attempt (not just timeouts)
#   - Timeout errors still get up to 3 retry attempts
# v3.4 - Add retry mechanism for timeout errors & optimize navigation wait strategy
#   - Changed wait_until from 'networkidle' to 'domcontentloaded' for faster, more reliable navigation
#   - Added 3-attempt retry logic for timeout errors (retries entire report from navigation)
#   - Browser layer: cdp_launcher.py (CDP detect + launch)
#   - Site layer: sites/ (website navigation)
#   - Crawler layer: crawlers/ (data extraction)
#
# Supported sites:
# - guanjia: 美团管家 (pos.meituan.com)
#   - equity_package_sales: 权益包售卖汇总表
#   - business_summary: 综合营业统计
# - dianping: 大众点评商家后台 (e.dianping.com) [skeleton]

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
from src.browser.cdp_launcher import DEFAULT_CDP_PORT, DEFAULT_PROFILE_DIR, DEFAULT_STARTUP_URL
from src.sites import MeituanGuanjiaSite, DianpingSite
from src.crawlers.guanjia import EquityPackageSalesCrawler, BusinessSummaryCrawler, DishSalesCrawler
from src.utils import get_yesterday, get_today
from src.config import CDP_URL, LOG_DIR, SUPABASE_ENABLED
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


# Site registry - maps site names to their classes and startup URLs
SITES = {
    "guanjia": {
        "class": MeituanGuanjiaSite,
        "name": "美团管家",
        "startup_url": "https://pos.meituan.com",
        "reports": {
            "equity_package_sales": EquityPackageSalesCrawler,
            "business_summary": BusinessSummaryCrawler,
            "dish_sales": DishSalesCrawler
        }
    },
    "dianping": {
        "class": DianpingSite,
        "name": "大众点评商家后台",
        "startup_url": "https://e.dianping.com",
        "reports": {}  # TODO: Add crawlers as implemented
    }
}


async def main():
    """
    Main entry point - runs crawlers based on command line arguments.
    Supports multiple reports in a single run with --report all or --report r1 r2.
    """
    args = parse_args()

    logger.info("=" * 80)
    logger.info("Meituan/Dianping Multi-Site Crawler")
    logger.info("=" * 80)

    # Validate site
    site_key = args.site
    if site_key not in SITES:
        logger.error(f"Unknown site: {site_key}. Available: {list(SITES.keys())}")
        return

    site_config = SITES[site_key]
    logger.info(f"Site: {site_config['name']} ({site_key})")

    # Determine which reports to run
    available_reports = list(site_config["reports"].keys())
    if args.report == ["all"]:
        reports_to_run = available_reports
    else:
        # Validate all requested reports exist
        reports_to_run = []
        for report_key in args.report:
            if report_key not in site_config["reports"]:
                logger.error(f"Unknown report: {report_key}. Available for {site_key}: {available_reports}")
                return
            reports_to_run.append(report_key)

    logger.info(f"Reports to run: {reports_to_run}")

    # Determine target date
    target_date = args.date if args.date else get_yesterday()
    end_date = args.end_date or target_date
    logger.info(f"Date range: {target_date} to {end_date}")

    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager()

    # Ensure Chrome CDP is available
    cdp_port = DEFAULT_CDP_PORT
    if args.cdp:
        cdp_url = args.cdp
        if ":" in cdp_url.split("//")[-1]:
            cdp_port = int(cdp_url.split(":")[-1])
    else:
        cdp_url = CDP_URL

    # Use site-specific startup URL
    startup_url = site_config["startup_url"]

    logger.info("Ensuring Chrome CDP is available...")
    cdp_success, was_launched = await ensure_cdp_available(
        port=cdp_port,
        profile_dir=DEFAULT_PROFILE_DIR,
        startup_url=startup_url
    )

    if not cdp_success:
        logger.error("Failed to initialize Chrome CDP")
        return

    if was_launched:
        logger.info("Launched new Chrome instance")
        logger.info(f"Please login to {site_config['name']} in the browser, then run again.")
        return
    else:
        logger.info("Reusing existing Chrome CDP session")

    # Connect to browser
    logger.info(f"Connecting to Chrome via CDP: {cdp_url}")
    session = CDPSession(cdp_url)

    # Track results for all reports
    all_results = []

    try:
        await session.connect()
        # Get page matching the site's URL pattern
        url_pattern = site_config["startup_url"].replace("https://", "").split("/")[0]
        page = await session.get_page(url_pattern=url_pattern)
        logger.info(f"Connected. Current URL: {page.url}")

        # Initialize site
        site_class = site_config["class"]
        site = site_class(page)

        # Run each report sequentially
        for report_idx, report_key in enumerate(reports_to_run):
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"REPORT {report_idx + 1}/{len(reports_to_run)}: {report_key}")
            logger.info("=" * 60)

            results = {
                "site": site_key,
                "report": report_key,
                "date_range": f"{target_date} to {end_date}",
                "success": False,
                "total_records": 0,
                "error": None,
                "start_time": datetime.now().isoformat()
            }

            # Retry mechanism for timeout errors
            MAX_RETRIES = 3
            for attempt in range(MAX_RETRIES):
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{MAX_RETRIES} for {report_key}")

                try:
                    # Navigate to report using site layer
                    logger.info(f"Navigating to report: {report_key}")
                    if not args.skip_navigation:
                        nav_success = await site.navigate_to_report(report_key)
                        if not nav_success:
                            results["error"] = "Navigation failed"
                            # Don't retry navigation failures from other causes
                            break
                    else:
                        logger.info("SKIP_NAVIGATION: Using current page state")

                    # Get frame from site
                    frame = site.get_frame()

                    # Initialize and run crawler
                    crawler_class = site_config["reports"][report_key]
                    crawler = crawler_class(
                        page=page,
                        frame=frame,
                        db_manager=db,
                        target_date=target_date,
                        end_date=end_date,
                        skip_navigation=args.skip_navigation,
                        force_update=args.force
                    )

                    logger.info(f"Running {crawler_class.__name__}...")
                    result = await crawler.crawl()

                    if result["success"]:
                        logger.info("Crawl completed successfully")
                        record_count = result["data"].get("record_count", 0)
                        save_stats = result["data"].get("save_stats", {})
                        results["success"] = True
                        results["total_records"] = record_count
                        results["save_stats"] = save_stats

                        logger.info(
                            f"SQLite: {save_stats.get('inserted', 0)} inserted, "
                            f"{save_stats.get('updated', 0)} updated, "
                            f"{save_stats.get('skipped', 0)} skipped"
                        )

                        # Upload to Supabase
                        records = result["data"].get("records", [])
                        if records and not args.no_supabase:
                            logger.info("Uploading to Supabase...")
                            supabase_stats = upload_to_supabase(records, report_key)
                            results["supabase_stats"] = supabase_stats

                            logger.info(
                                f"Supabase: {supabase_stats.get('inserted', 0)} inserted, "
                                f"{supabase_stats.get('updated', 0)} updated, "
                                f"{supabase_stats.get('failed', 0)} failed"
                            )
                        elif args.no_supabase:
                            logger.info("Supabase upload skipped (--no-supabase)")

                        # Success - break retry loop
                        break
                    else:
                        error_msg = result.get("error")
                        logger.error(f"Crawl failed: {error_msg}")
                        results["error"] = error_msg

                        # Retry at least once for any error
                        if attempt < 1:
                            logger.info(f"Retrying {report_key} once for error: {error_msg}")
                            await asyncio.sleep(2)
                            continue
                        else:
                            # Already retried once, don't retry again for non-timeout errors
                            break

                except Exception as e:
                    error_msg = str(e)
                    is_timeout = "Timeout" in error_msg or "timeout" in error_msg.lower()

                    if is_timeout and attempt < MAX_RETRIES - 1:
                        logger.warning(f"Timeout error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                        logger.info(f"Retrying {report_key} from the beginning...")
                        await asyncio.sleep(2)  # Brief pause before retry
                        continue
                    else:
                        # Last attempt or non-timeout error
                        logger.error(f"Error in {report_key}: {e}", exc_info=True)
                        results["error"] = error_msg
                        break

            results["end_time"] = datetime.now().isoformat()
            all_results.append(results)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

    finally:
        logger.info("Closing browser connection...")
        await session.close()
        print_multi_summary(all_results)


def upload_to_supabase(records: List[Dict[str, Any]], report_type: str) -> Dict[str, Any]:
    """
    Upload records to Supabase with error handling.

    Args:
        records: List of records to upload
        report_type: Report type ('equity_package_sales', 'business_summary', or 'dish_sales')
    """
    try:
        supabase_mgr = SupabaseManager()

        if report_type == "equity_package_sales":
            stats = supabase_mgr.save_equity_package_sales(records)
        elif report_type == "business_summary":
            stats = supabase_mgr.save_business_summary(records)
        elif report_type == "dish_sales":
            stats = supabase_mgr.save_dish_sales(records)
        else:
            logger.warning(f"Unknown report type for Supabase: {report_type}")
            return {"inserted": 0, "updated": 0, "failed": 0, "skipped": len(records)}

        return stats
    except Exception as e:
        logger.error(f"Supabase upload error: {e}")
        return {"inserted": 0, "updated": 0, "failed": len(records), "error": str(e)}


def print_multi_summary(all_results: List[Dict[str, Any]]) -> None:
    """Print summary for multiple reports."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("CRAWL SUMMARY")
    logger.info("=" * 80)

    if not all_results:
        logger.info("No reports were run.")
        return

    total_records = 0
    total_success = 0

    for results in all_results:
        report_name = results.get('report', 'unknown')
        status = 'SUCCESS' if results['success'] else 'FAILED'
        records = results.get('total_records', 0)
        total_records += records

        if results['success']:
            total_success += 1

        logger.info(f"  [{status}] {report_name}: {records} records")

        save_stats = results.get('save_stats', {})
        if save_stats:
            logger.info(f"          SQLite: {save_stats.get('inserted', 0)} ins, "
                       f"{save_stats.get('updated', 0)} upd, "
                       f"{save_stats.get('skipped', 0)} skip")

        supabase_stats = results.get('supabase_stats', {})
        if supabase_stats:
            logger.info(f"          Supabase: {supabase_stats.get('inserted', 0)} ins, "
                       f"{supabase_stats.get('updated', 0)} upd, "
                       f"{supabase_stats.get('failed', 0)} fail")

        if results.get('error'):
            logger.info(f"          Error: {results['error']}")

    logger.info("-" * 80)
    logger.info(f"TOTAL: {total_success}/{len(all_results)} reports succeeded, {total_records} records")
    logger.info("=" * 80)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Meituan/Dianping Multi-Site Crawler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 美团管家 - 权益包售卖汇总表 (default)
  python src/main.py

  # Run both crawlers sequentially
  python src/main.py --report all

  # Run specific crawlers
  python src/main.py --report equity_package_sales business_summary

  # 3-day lookback for cron
  python src/main.py --report all --date 2025-12-15 --end-date 2025-12-17

  # Specific date
  python src/main.py --date 2025-12-13

  # Skip navigation (debugging)
  python src/main.py --skip-navigation

  # Skip Supabase upload
  python src/main.py --no-supabase
        """
    )

    parser.add_argument(
        '--site',
        type=str,
        default='guanjia',
        choices=list(SITES.keys()),
        help='Target site (default: guanjia)'
    )

    parser.add_argument(
        '--report',
        type=str,
        nargs='+',
        default=['equity_package_sales'],
        help='Report(s) to crawl. Use "all" for all reports (default: equity_package_sales)'
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
        help='Target/start date YYYY-MM-DD (default: yesterday)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date for range (default: same as start)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-crawl'
    )

    parser.add_argument(
        '--skip-navigation',
        action='store_true',
        help='Skip page navigation (for debugging)'
    )

    parser.add_argument(
        '--no-supabase',
        action='store_true',
        help='Skip Supabase upload'
    )

    return parser.parse_args()


if __name__ == '__main__':
    asyncio.run(main())
