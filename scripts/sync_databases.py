#!/usr/bin/env python3
"""
Database Sync Tool - Bidirectional sync between local SQLite and Supabase
v1.0 - Supports equity_package_sales and business_summary tables

Usage:
    python scripts/sync_databases.py                    # Sync all tables both ways
    python scripts/sync_databases.py --pull             # Pull from Supabase to local only
    python scripts/sync_databases.py --push             # Push from local to Supabase only
    python scripts/sync_databases.py --table equity     # Sync only equity_package_sales
    python scripts/sync_databases.py --table business   # Sync only business_summary
    python scripts/sync_databases.py --dry-run          # Show what would be synced without doing it
"""

import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_manager import DatabaseManager
from database.supabase_manager import SupabaseManager, MEITUAN_STORE_NAME_MAP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseSync:
    """Handles bidirectional sync between SQLite and Supabase."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = DatabaseManager()
        self.supabase = SupabaseManager()

        # Stats
        self.stats = {
            'equity_package_sales': {'pulled': 0, 'pushed': 0, 'skipped': 0},
            'business_summary': {'pulled': 0, 'pushed': 0, 'skipped': 0}
        }

    def sync_all(self, direction: str = 'both'):
        """
        Sync all tables.

        Args:
            direction: 'both', 'pull' (cloud->local), or 'push' (local->cloud)
        """
        logger.info("=" * 60)
        logger.info(f"DATABASE SYNC - Direction: {direction.upper()}")
        logger.info("=" * 60)

        if direction in ('both', 'pull'):
            self.pull_equity_package_sales()
            self.pull_business_summary()

        if direction in ('both', 'push'):
            self.push_equity_package_sales()
            self.push_business_summary()

        self._print_summary()

    def sync_equity_package_sales(self, direction: str = 'both'):
        """Sync only equity_package_sales table."""
        logger.info("Syncing equity_package_sales...")

        if direction in ('both', 'pull'):
            self.pull_equity_package_sales()
        if direction in ('both', 'push'):
            self.push_equity_package_sales()

    def sync_business_summary(self, direction: str = 'both'):
        """Sync only business_summary table."""
        logger.info("Syncing business_summary...")

        if direction in ('both', 'pull'):
            self.pull_business_summary()
        if direction in ('both', 'push'):
            self.push_business_summary()

    # ==================== PULL (Supabase -> SQLite) ====================

    def pull_equity_package_sales(self):
        """Pull equity_package_sales from Supabase to local SQLite."""
        logger.info("\n--- Pulling equity_package_sales from Supabase ---")

        try:
            # Get all records from Supabase with restaurant info
            result = self.supabase._client.table('mt_equity_package_sales').select(
                'date, package_name, unit_price, quantity_sold, total_sales, '
                'refund_quantity, refund_amount, '
                'master_restaurant(meituan_org_code, restaurant_name)'
            ).execute()

            cloud_records = result.data
            logger.info(f"Found {len(cloud_records)} records in Supabase")

            # Get local records for comparison
            local_keys = self._get_local_equity_keys()
            logger.info(f"Found {len(local_keys)} records in local SQLite")

            # Find records missing locally
            records_to_add = []
            for record in cloud_records:
                restaurant = record.get('master_restaurant', {})
                org_code = restaurant.get('meituan_org_code') if restaurant else None
                store_name = restaurant.get('restaurant_name') if restaurant else None

                if not org_code:
                    continue

                key = (org_code, record['date'], record['package_name'])

                if key not in local_keys:
                    records_to_add.append({
                        'org_code': org_code,
                        'store_name': store_name or org_code,
                        'date': record['date'],
                        'package_name': record['package_name'],
                        'unit_price': record.get('unit_price', 99.0) or 99.0,
                        'quantity_sold': record.get('quantity_sold', 0) or 0,
                        'total_sales': record.get('total_sales', 0) or 0,
                        'refund_quantity': record.get('refund_quantity', 0) or 0,
                        'refund_amount': record.get('refund_amount', 0) or 0
                    })

            logger.info(f"Found {len(records_to_add)} records missing locally")

            if records_to_add and not self.dry_run:
                stats = self.db.save_equity_package_sales(records_to_add)
                self.stats['equity_package_sales']['pulled'] = stats['inserted'] + stats['updated']
            elif records_to_add:
                logger.info(f"[DRY RUN] Would add {len(records_to_add)} records to local")
                self.stats['equity_package_sales']['pulled'] = len(records_to_add)

        except Exception as e:
            logger.error(f"Error pulling equity_package_sales: {e}")

    def pull_business_summary(self):
        """Pull business_summary from Supabase to local SQLite."""
        logger.info("\n--- Pulling business_summary from Supabase ---")

        try:
            # Get all records from Supabase
            result = self.supabase._client.table('mt_business_summary').select(
                '*, master_restaurant(restaurant_name)'
            ).execute()

            cloud_records = result.data
            logger.info(f"Found {len(cloud_records)} records in Supabase")

            # Get local records for comparison
            local_keys = self._get_local_business_keys()
            logger.info(f"Found {len(local_keys)} records in local SQLite")

            # Reverse mapping: Supabase name -> Meituan name
            reverse_name_map = {v: k for k, v in MEITUAN_STORE_NAME_MAP.items()}

            # Find records missing locally
            records_to_add = []
            for record in cloud_records:
                restaurant = record.get('master_restaurant', {})
                supabase_name = restaurant.get('restaurant_name') if restaurant else None
                business_date = record.get('营业日期')

                if not supabase_name or not business_date:
                    continue

                # Convert Supabase name back to Meituan name
                meituan_name = reverse_name_map.get(supabase_name, supabase_name)
                key = (meituan_name, business_date)

                if key not in local_keys:
                    # Handle composition_data - convert dict to JSON string if needed
                    composition_data = record.get('构成数据', '{}')
                    if isinstance(composition_data, dict):
                        composition_data = json.dumps(composition_data, ensure_ascii=False)

                    records_to_add.append({
                        'city': record.get('城市', ''),
                        'store_name': meituan_name,
                        'business_date': business_date,
                        'store_created_at': record.get('门店创建时间', ''),
                        'operating_days': record.get('营业天数', 0),
                        'revenue': record.get('营业额', 0),
                        'discount_amount': record.get('折扣金额', 0),
                        'business_income': record.get('营业收入', 0),
                        'order_count': record.get('订单数', 0),
                        'diner_count': record.get('就餐人数', 0),
                        'table_count': record.get('开台数', 0),
                        'per_capita_before_discount': record.get('折前人均', 0),
                        'per_capita_after_discount': record.get('折后人均', 0),
                        'avg_order_before_discount': record.get('折前单均', 0),
                        'avg_order_after_discount': record.get('折后单均', 0),
                        'table_opening_rate': record.get('开台率', ''),
                        'table_turnover_rate': record.get('翻台率', 0),
                        'occupancy_rate': record.get('上座率', ''),
                        'avg_dining_time': record.get('平均用餐时长', 0),
                        'composition_data': composition_data
                    })

            logger.info(f"Found {len(records_to_add)} records missing locally")

            if records_to_add and not self.dry_run:
                stats = self.db.save_business_summary(records_to_add, force_update=False)
                self.stats['business_summary']['pulled'] = stats['inserted'] + stats['updated']
            elif records_to_add:
                logger.info(f"[DRY RUN] Would add {len(records_to_add)} records to local")
                self.stats['business_summary']['pulled'] = len(records_to_add)

        except Exception as e:
            logger.error(f"Error pulling business_summary: {e}")

    # ==================== PUSH (SQLite -> Supabase) ====================

    def push_equity_package_sales(self):
        """Push equity_package_sales from local SQLite to Supabase."""
        logger.info("\n--- Pushing equity_package_sales to Supabase ---")

        try:
            # Get all local records
            local_records = self.db.get_equity_sales()
            logger.info(f"Found {len(local_records)} records in local SQLite")

            # Get cloud record keys for comparison
            cloud_keys = self._get_cloud_equity_keys()
            logger.info(f"Found {len(cloud_keys)} records in Supabase")

            # Find records missing in cloud
            records_to_push = []
            for record in local_records:
                key = (record['org_code'], record['date'], record['package_name'])
                if key not in cloud_keys:
                    records_to_push.append(record)

            logger.info(f"Found {len(records_to_push)} records missing in Supabase")

            if records_to_push and not self.dry_run:
                stats = self.supabase.save_equity_package_sales(records_to_push)
                self.stats['equity_package_sales']['pushed'] = stats.get('inserted', 0)
            elif records_to_push:
                logger.info(f"[DRY RUN] Would push {len(records_to_push)} records to Supabase")
                self.stats['equity_package_sales']['pushed'] = len(records_to_push)

        except Exception as e:
            logger.error(f"Error pushing equity_package_sales: {e}")

    def push_business_summary(self):
        """Push business_summary from local SQLite to Supabase."""
        logger.info("\n--- Pushing business_summary to Supabase ---")

        try:
            # Get all local records
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM mt_business_summary")
                columns = [desc[0] for desc in cursor.description]
                local_records = [dict(zip(columns, row)) for row in cursor.fetchall()]

            logger.info(f"Found {len(local_records)} records in local SQLite")

            # Get cloud record keys for comparison
            cloud_keys = self._get_cloud_business_keys()
            logger.info(f"Found {len(cloud_keys)} records in Supabase")

            # Find records missing in cloud
            records_to_push = []
            for record in local_records:
                store_name = record.get('store_name', '')
                business_date = record.get('business_date', '')
                key = (store_name, business_date)

                if key not in cloud_keys:
                    records_to_push.append(record)

            logger.info(f"Found {len(records_to_push)} records missing in Supabase")

            if records_to_push and not self.dry_run:
                stats = self.supabase.save_business_summary(records_to_push)
                self.stats['business_summary']['pushed'] = stats.get('inserted', 0) + stats.get('updated', 0)
            elif records_to_push:
                logger.info(f"[DRY RUN] Would push {len(records_to_push)} records to Supabase")
                self.stats['business_summary']['pushed'] = len(records_to_push)

        except Exception as e:
            logger.error(f"Error pushing business_summary: {e}")

    # ==================== Helper Methods ====================

    def _get_local_equity_keys(self) -> Set[Tuple[str, str, str]]:
        """Get set of (org_code, date, package_name) keys from local DB."""
        keys = set()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT org_code, date, package_name FROM mt_equity_package_sales")
                for row in cursor.fetchall():
                    keys.add((row[0], row[1], row[2]))
        except Exception as e:
            logger.error(f"Error getting local equity keys: {e}")
        return keys

    def _get_local_business_keys(self) -> Set[Tuple[str, str]]:
        """Get set of (store_name, business_date) keys from local DB."""
        keys = set()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT store_name, business_date FROM mt_business_summary")
                for row in cursor.fetchall():
                    keys.add((row[0], row[1]))
        except Exception as e:
            logger.error(f"Error getting local business keys: {e}")
        return keys

    def _get_cloud_equity_keys(self) -> Set[Tuple[str, str, str]]:
        """Get set of (org_code, date, package_name) keys from Supabase."""
        keys = set()
        try:
            self.supabase._load_restaurant_cache()

            result = self.supabase._client.table('mt_equity_package_sales').select(
                'date, package_name, master_restaurant(meituan_org_code)'
            ).execute()

            for row in result.data:
                restaurant = row.get('master_restaurant', {})
                org_code = restaurant.get('meituan_org_code') if restaurant else None
                if org_code:
                    keys.add((org_code, row['date'], row['package_name']))
        except Exception as e:
            logger.error(f"Error getting cloud equity keys: {e}")
        return keys

    def _get_cloud_business_keys(self) -> Set[Tuple[str, str]]:
        """Get set of (store_name, business_date) keys from Supabase."""
        keys = set()
        try:
            result = self.supabase._client.table('mt_business_summary').select(
                '营业日期, master_restaurant(restaurant_name)'
            ).execute()

            # Reverse mapping
            reverse_name_map = {v: k for k, v in MEITUAN_STORE_NAME_MAP.items()}

            for row in result.data:
                restaurant = row.get('master_restaurant', {})
                supabase_name = restaurant.get('restaurant_name') if restaurant else None
                business_date = row.get('营业日期')

                if supabase_name and business_date:
                    # Convert to Meituan name for comparison
                    meituan_name = reverse_name_map.get(supabase_name, supabase_name)
                    keys.add((meituan_name, business_date))
        except Exception as e:
            logger.error(f"Error getting cloud business keys: {e}")
        return keys

    def _print_summary(self):
        """Print sync summary."""
        logger.info("\n" + "=" * 60)
        logger.info("SYNC SUMMARY")
        logger.info("=" * 60)

        for table, stats in self.stats.items():
            pulled = stats['pulled']
            pushed = stats['pushed']
            logger.info(f"  {table}:")
            logger.info(f"    Pulled (cloud → local): {pulled}")
            logger.info(f"    Pushed (local → cloud): {pushed}")

        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Sync local SQLite and Supabase databases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/sync_databases.py                    # Sync all tables both ways
  python scripts/sync_databases.py --pull             # Pull from Supabase to local
  python scripts/sync_databases.py --push             # Push from local to Supabase
  python scripts/sync_databases.py --table equity     # Sync only equity_package_sales
  python scripts/sync_databases.py --table business   # Sync only business_summary
  python scripts/sync_databases.py --dry-run          # Show what would be synced
        """
    )

    parser.add_argument(
        '--pull',
        action='store_true',
        help='Pull from Supabase to local only'
    )

    parser.add_argument(
        '--push',
        action='store_true',
        help='Push from local to Supabase only'
    )

    parser.add_argument(
        '--table',
        choices=['equity', 'business', 'all'],
        default='all',
        help='Which table to sync (default: all)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without making changes'
    )

    args = parser.parse_args()

    # Determine direction
    if args.pull and args.push:
        direction = 'both'
    elif args.pull:
        direction = 'pull'
    elif args.push:
        direction = 'push'
    else:
        direction = 'both'

    # Run sync
    sync = DatabaseSync(dry_run=args.dry_run)

    if args.table == 'equity':
        sync.sync_equity_package_sales(direction)
    elif args.table == 'business':
        sync.sync_business_summary(direction)
    else:
        sync.sync_all(direction)

    sync._print_summary()


if __name__ == '__main__':
    main()
