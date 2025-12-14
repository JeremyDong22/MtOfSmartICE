"""
Daily Crawler - Main entry point for automated daily crawling

This script:
1. Connects to Chrome via CDP
2. Gets yesterday's date (or override)
3. Gets all stores from dashboard
4. For each store:
   - Switch to store
   - Run MembershipCrawler
   - Save results
5. Print summary
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

from src.browser import CDPSession, StoreNavigator
from src.crawlers.membership_crawler import MembershipCrawler
from src.utils import get_yesterday, get_today
from src.config import CDP_URL, LOG_DIR
from database.db_manager import DatabaseManager

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
    Daily crawler - runs through all stores.
    """
    args = parse_args()

    logger.info("=" * 80)
    logger.info("Meituan Merchant Backend Daily Crawler")
    logger.info("=" * 80)

    # Determine target date
    target_date = args.date if args.date else get_yesterday()
    logger.info(f"Target date: {target_date}")

    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager()

    # Initialize CDP session
    cdp_url = args.cdp if args.cdp else CDP_URL
    logger.info(f"Connecting to Chrome via CDP: {cdp_url}")
    session = CDPSession(cdp_url)

    results = {
        "date": target_date,
        "success": [],
        "failed": [],
        "total_records": 0,
        "start_time": datetime.now().isoformat()
    }

    try:
        # Connect to browser
        await session.connect()
        page = await session.get_page()
        logger.info(f"Connected to browser. Current URL: {page.url}")

        # Initialize store navigator
        navigator = StoreNavigator(page)

        # Navigate to dashboard
        logger.info("Navigating to dashboard...")
        if not await navigator.navigate_to_dashboard():
            logger.error("Failed to navigate to dashboard")
            return

        # Get all stores
        logger.info("Getting all available stores...")
        stores = await navigator.get_all_stores()

        if not stores:
            logger.warning("No stores found. Using fallback store list from database.")
            # Fallback to database stores
            stores = db.get_all_stores()
            stores = [{"store_id": s["merchant_id"], "store_name": s["store_name"]} for s in stores]

        if not stores:
            logger.error("No stores available. Cannot proceed.")
            return

        logger.info(f"Found {len(stores)} stores to process")

        # Filter stores if specified
        if args.store:
            stores = [s for s in stores if s["store_id"] == args.store]
            if not stores:
                logger.error(f"Store {args.store} not found")
                return
            logger.info(f"Filtered to single store: {stores[0]['store_name']}")

        # Process each store
        for idx, store in enumerate(stores, 1):
            store_id = store["store_id"]
            store_name = store["store_name"]

            logger.info("")
            logger.info("=" * 80)
            logger.info(f"Processing store {idx}/{len(stores)}: {store_name}")
            logger.info(f"Store ID: {store_id}")
            logger.info("=" * 80)

            try:
                # Check if already crawled (skip if not forcing)
                if not args.force and db.data_exists(store_id, target_date, "membership_card"):
                    logger.info(f"Data already exists for {store_name} on {target_date} - skipping")
                    continue

                # Switch to store
                logger.info(f"Switching to store: {store_name}")
                if not await navigator.switch_to_store(store_id, store_name):
                    logger.error(f"Failed to switch to store {store_name}")
                    results["failed"].append({
                        "store_id": store_id,
                        "store_name": store_name,
                        "error": "Failed to switch store"
                    })
                    continue

                # Wait for page to update
                await asyncio.sleep(2)

                # Get the iframe for the crawler
                frame = await get_report_frame(page)

                # Initialize crawler
                crawler = MembershipCrawler(
                    page=page,
                    frame=frame,
                    db_manager=db,
                    target_date=target_date
                )

                # Run crawler
                logger.info(f"Starting crawl for {store_name}...")
                result = await crawler.crawl(store_id, store_name)

                if result["success"]:
                    logger.info(f"Successfully crawled {store_name}")
                    results["success"].append({
                        "store_id": store_id,
                        "store_name": store_name,
                        "records": result["data"].get("order_count", 0)
                    })
                    results["total_records"] += result["data"].get("order_count", 0)
                else:
                    logger.error(f"Crawl failed for {store_name}: {result.get('error')}")
                    results["failed"].append({
                        "store_id": store_id,
                        "store_name": store_name,
                        "error": result.get("error", "Unknown error")
                    })

                # Navigate back to dashboard after each store's crawl
                # This ensures we're on a page where store switching works
                logger.info("Navigating back to dashboard for next store...")
                await navigator.navigate_to_dashboard()
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error processing store {store_name}: {e}", exc_info=True)
                results["failed"].append({
                    "store_id": store_id,
                    "store_name": store_name,
                    "error": str(e)
                })

            # Brief pause between stores
            if idx < len(stores):
                await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

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
    logger.info(f"Date: {results['date']}")
    logger.info(f"Total records extracted: {results['total_records']}")
    logger.info(f"Successful stores: {len(results['success'])}")
    logger.info(f"Failed stores: {len(results['failed'])}")

    if results['success']:
        logger.info("")
        logger.info("Successful stores:")
        for item in results['success']:
            logger.info(f"  - {item['store_name']} ({item['store_id']}): {item['records']} records")

    if results['failed']:
        logger.info("")
        logger.info("Failed stores:")
        for item in results['failed']:
            logger.info(f"  - {item['store_name']} ({item['store_id']}): {item['error']}")

    logger.info("=" * 80)
    logger.info(f"Start time: {results['start_time']}")
    logger.info(f"End time: {results['end_time']}")
    logger.info("=" * 80)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Meituan Merchant Backend Daily Crawler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run daily crawl for yesterday's data
  python src/main.py

  # Run for specific date
  python src/main.py --date 2025-12-13

  # Run for specific store
  python src/main.py --store 58188193

  # Use custom CDP URL
  python src/main.py --cdp http://localhost:9223

  # Force re-crawl (ignore existing data)
  python src/main.py --force
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
        help='Target date in YYYY-MM-DD format (default: yesterday)'
    )

    parser.add_argument(
        '--store',
        type=str,
        default=None,
        help='Crawl specific store only (merchant ID)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-crawl even if data exists'
    )

    return parser.parse_args()


if __name__ == '__main__':
    asyncio.run(main())
