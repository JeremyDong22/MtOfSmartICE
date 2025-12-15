"""
Supabase Database Manager for Meituan Crawler
v1.1 - Updated to use anon key by default (no service role needed)

Key Features:
- Uploads equity package sales data to Supabase
- Gracefully handles unknown org_codes (logs warning, skips record, continues)
- Error isolation: one failed record won't affect others
- Conditional update: only updates if new values are higher
- Uses anon key by default - no service role key required

Usage:
    from database.supabase_manager import SupabaseManager

    manager = SupabaseManager()
    stats = manager.save_equity_package_sales(records)
    # stats = {"inserted": N, "updated": N, "skipped": N, "unknown_stores": [...]}
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from supabase import create_client, Client

# Import config for default values
from src.config import SUPABASE_URL as DEFAULT_URL, SUPABASE_KEY as DEFAULT_KEY

# Configure logging
logger = logging.getLogger(__name__)


class SupabaseManager:
    """
    Manages Supabase database operations for Meituan equity package sales data.
    Implements robust error handling to ensure one failed record doesn't block others.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """
        Initialize the Supabase manager.

        Args:
            supabase_url: Supabase project URL (defaults to config)
            supabase_key: Supabase API key (defaults to anon key from config)
        """
        self.supabase_url = supabase_url or DEFAULT_URL
        self.supabase_key = supabase_key or DEFAULT_KEY

        # Initialize client - anon key is always available
        self._client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"Supabase client initialized for: {self.supabase_url}")

        # Cache for org_code -> restaurant_id mappings
        self._restaurant_cache: Dict[str, str] = {}
        self._cache_loaded = False

    def _load_restaurant_cache(self) -> None:
        """
        Load restaurant mappings (meituan_org_code -> restaurant_id) into cache.
        Called once on first use to minimize API calls.
        """
        if self._cache_loaded:
            return

        try:
            result = self._client.table('master_restaurant').select(
                'id, meituan_org_code, restaurant_name'
            ).not_.is_('meituan_org_code', 'null').execute()

            for row in result.data:
                org_code = row['meituan_org_code']
                restaurant_id = row['id']
                self._restaurant_cache[org_code] = restaurant_id
                logger.debug(
                    f"Cached mapping: {org_code} -> {restaurant_id} "
                    f"({row.get('restaurant_name', 'unknown')})"
                )

            self._cache_loaded = True
            logger.info(f"Loaded {len(self._restaurant_cache)} restaurant mappings from Supabase")

        except Exception as e:
            logger.error(f"Failed to load restaurant mappings: {e}")

    def get_restaurant_id(self, org_code: str) -> Optional[str]:
        """
        Get restaurant UUID for a Meituan org_code.

        Args:
            org_code: Meituan organization code (e.g., "MD00007")

        Returns:
            Restaurant UUID if found, None otherwise
        """
        self._load_restaurant_cache()
        return self._restaurant_cache.get(org_code)

    def save_equity_package_sales(
        self,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save equity package sales records to Supabase with robust error handling.

        IMPORTANT: This method implements error isolation - each record is processed
        independently. If one record fails (e.g., unknown store), other records
        continue to be processed normally.

        Duplicate Handling Logic:
        - If record doesn't exist: INSERT new record
        - If record exists AND (new quantity > old OR new sales > old): UPDATE
        - If record exists AND new values are NOT higher: SKIP

        Args:
            records: List of record dictionaries with keys:
                - org_code: Meituan organization code
                - store_name: Store name (for logging only)
                - date: Date in YYYY-MM-DD format
                - package_name: Package name
                - unit_price: Unit price
                - quantity_sold: Quantity sold
                - total_sales: Total sales amount
                - refund_quantity: Refund quantity (optional)
                - refund_amount: Refund amount (optional)

        Returns:
            Dictionary with stats:
            {
                "inserted": int,      # New records inserted
                "updated": int,       # Existing records updated (higher values)
                "skipped": int,       # Existing records skipped (values not higher)
                "failed": int,        # Records that failed to process
                "unknown_stores": [   # List of unrecognized org_codes
                    {"org_code": "MD00012", "store_name": "新门店"}
                ]
            }
        """
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "unknown_stores": []
        }

        if not records:
            logger.warning("No records to save")
            return stats

        # Pre-load restaurant mappings
        self._load_restaurant_cache()

        # Track unique unknown stores to avoid duplicate warnings
        seen_unknown = set()

        for record in records:
            try:
                org_code = record['org_code']
                store_name = record.get('store_name', 'unknown')
                date = record['date']
                package_name = record['package_name']
                new_quantity = record['quantity_sold']
                new_sales = record['total_sales']

                # Get restaurant_id from cache
                restaurant_id = self._restaurant_cache.get(org_code)

                if not restaurant_id:
                    # Unknown store - log warning but DON'T fail
                    # This is the key robustness feature
                    if org_code not in seen_unknown:
                        logger.warning(
                            f"未知门店 (Unknown store): {org_code} - {store_name}. "
                            f"跳过该记录，继续处理其他门店。"
                        )
                        stats["unknown_stores"].append({
                            "org_code": org_code,
                            "store_name": store_name
                        })
                        seen_unknown.add(org_code)
                    stats["skipped"] += 1
                    continue  # SKIP this record, continue with others

                # Check if record exists and get current values
                existing = self._get_existing_record(restaurant_id, date, package_name)

                if existing is None:
                    # No existing record - INSERT new
                    self._insert_record(restaurant_id, record)
                    stats["inserted"] += 1
                    logger.debug(
                        f"INSERT: {org_code}/{date}/{package_name} - "
                        f"qty={new_quantity}, sales={new_sales}"
                    )

                else:
                    # Record exists - check if new values are higher
                    old_quantity = existing.get('quantity_sold', 0)
                    old_sales = float(existing.get('total_sales', 0))

                    if new_quantity > old_quantity or new_sales > old_sales:
                        # New values are higher - UPDATE
                        self._update_record(existing['id'], record)
                        stats["updated"] += 1
                        logger.debug(
                            f"UPDATE: {org_code}/{date}/{package_name} - "
                            f"qty: {old_quantity}->{new_quantity}, "
                            f"sales: {old_sales}->{new_sales}"
                        )
                    else:
                        # New values are NOT higher - SKIP
                        stats["skipped"] += 1
                        logger.debug(
                            f"SKIP: {org_code}/{date}/{package_name} - "
                            f"existing qty={old_quantity} >= new={new_quantity}"
                        )

            except Exception as e:
                # Error isolation: log error, increment failed counter, continue
                logger.error(
                    f"处理记录失败 {record.get('org_code', 'unknown')}"
                    f"/{record.get('date', 'unknown')}"
                    f"/{record.get('package_name', 'unknown')}: {e}"
                )
                stats["failed"] += 1
                continue  # Continue processing other records

        # Log summary
        total = sum([stats["inserted"], stats["updated"], stats["skipped"], stats["failed"]])
        logger.info(
            f"Supabase处理完成: {total} 条记录 - "
            f"插入:{stats['inserted']} 更新:{stats['updated']} "
            f"跳过:{stats['skipped']} 失败:{stats['failed']}"
        )

        if stats["unknown_stores"]:
            logger.warning(
                f"发现 {len(stats['unknown_stores'])} 个未知门店，请在 master_restaurant 表中添加映射: "
                f"{[s['org_code'] for s in stats['unknown_stores']]}"
            )

        return stats

    def _get_existing_record(
        self,
        restaurant_id: str,
        date: str,
        package_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing record by restaurant_id + date + package_name.

        Args:
            restaurant_id: Restaurant UUID
            date: Date string (YYYY-MM-DD)
            package_name: Package name

        Returns:
            Record dict if found, None otherwise
        """
        try:
            result = self._client.table('mt_equity_package_sales').select(
                'id, quantity_sold, total_sales'
            ).eq(
                'restaurant_id', restaurant_id
            ).eq(
                'date', date
            ).eq(
                'package_name', package_name
            ).execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"查询现有记录失败: {e}")
            return None

    def _insert_record(self, restaurant_id: str, record: Dict[str, Any]) -> None:
        """
        Insert a new equity package sales record.

        Args:
            restaurant_id: Restaurant UUID
            record: Record data
        """
        data = {
            'restaurant_id': restaurant_id,
            'date': record['date'],
            'package_name': record['package_name'],
            'unit_price': float(record['unit_price']),
            'quantity_sold': int(record['quantity_sold']),
            'total_sales': float(record['total_sales']),
            'refund_quantity': int(record.get('refund_quantity', 0)),
            'refund_amount': float(record.get('refund_amount', 0.0)),
        }

        self._client.table('mt_equity_package_sales').insert(data).execute()

    def _update_record(self, record_id: str, record: Dict[str, Any]) -> None:
        """
        Update an existing equity package sales record.

        Args:
            record_id: Existing record UUID
            record: New record data
        """
        data = {
            'unit_price': float(record['unit_price']),
            'quantity_sold': int(record['quantity_sold']),
            'total_sales': float(record['total_sales']),
            'refund_quantity': int(record.get('refund_quantity', 0)),
            'refund_amount': float(record.get('refund_amount', 0.0)),
            'updated_at': datetime.utcnow().isoformat()
        }

        self._client.table('mt_equity_package_sales').update(data).eq('id', record_id).execute()

    def get_equity_sales(
        self,
        org_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query equity package sales with optional filters.

        Args:
            org_code: Filter by Meituan organization code
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)

        Returns:
            List of sales records
        """
        try:
            # Start building query
            query = self._client.table('mt_equity_package_sales').select(
                '*, master_restaurant!inner(restaurant_name, meituan_org_code)'
            )

            # Apply filters
            if org_code:
                restaurant_id = self.get_restaurant_id(org_code)
                if restaurant_id:
                    query = query.eq('restaurant_id', restaurant_id)
                else:
                    logger.warning(f"Unknown org_code: {org_code}")
                    return []

            if start_date:
                query = query.gte('date', start_date)

            if end_date:
                query = query.lte('date', end_date)

            # Order by date desc
            query = query.order('date', desc=True)

            result = query.execute()

            # Transform results
            records = []
            for row in result.data:
                restaurant = row.get('master_restaurant', {})
                records.append({
                    'id': row['id'],
                    'org_code': restaurant.get('meituan_org_code', ''),
                    'store_name': restaurant.get('restaurant_name', ''),
                    'date': row['date'],
                    'package_name': row['package_name'],
                    'unit_price': row['unit_price'],
                    'quantity_sold': row['quantity_sold'],
                    'total_sales': row['total_sales'],
                    'refund_quantity': row.get('refund_quantity', 0),
                    'refund_amount': row.get('refund_amount', 0),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at')
                })

            logger.info(f"Retrieved {len(records)} equity sales records from Supabase")
            return records

        except Exception as e:
            logger.error(f"Error retrieving equity sales: {e}")
            return []

    def data_exists(
        self,
        org_code: str,
        date: str,
        package_name: str
    ) -> bool:
        """
        Check if a specific record already exists.

        Args:
            org_code: Organization code
            date: Date in YYYY-MM-DD format
            package_name: Package name

        Returns:
            True if record exists, False otherwise
        """
        restaurant_id = self.get_restaurant_id(org_code)
        if not restaurant_id:
            return False

        existing = self._get_existing_record(restaurant_id, date, package_name)
        return existing is not None

    def refresh_restaurant_cache(self) -> None:
        """Force refresh of restaurant mappings cache."""
        self._cache_loaded = False
        self._restaurant_cache.clear()
        self._load_restaurant_cache()
        logger.info(f"Restaurant cache refreshed: {len(self._restaurant_cache)} mappings")


# Example usage
if __name__ == "__main__":
    """Example usage and testing."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize manager
    manager = SupabaseManager()

    # Test restaurant mapping lookup
    print("\n=== Restaurant Mappings ===")
    for org_code in ["MD00006", "MD00007", "MD00008", "MD00012"]:
        restaurant_id = manager.get_restaurant_id(org_code)
        if restaurant_id:
            print(f"  {org_code} -> {restaurant_id[:8]}...")
        else:
            print(f"  {org_code} -> NOT FOUND (unknown store)")

    # Test save with mixed data (known and unknown stores)
    print("\n=== Testing Save with Unknown Store ===")
    test_records = [
        {
            "org_code": "MD00007",  # Known store
            "store_name": "宁桂杏山野烤肉（常熟世贸店）",
            "date": "2025-12-16",
            "package_name": "测试会员包",
            "unit_price": 99.0,
            "quantity_sold": 1,
            "total_sales": 99.0
        },
        {
            "org_code": "MD00099",  # Unknown store - should be skipped gracefully
            "store_name": "未知测试门店",
            "date": "2025-12-16",
            "package_name": "测试会员包",
            "unit_price": 99.0,
            "quantity_sold": 1,
            "total_sales": 99.0
        }
    ]

    stats = manager.save_equity_package_sales(test_records)
    print(f"\nResults: {stats}")
    print(f"  - Unknown stores detected: {stats['unknown_stores']}")
