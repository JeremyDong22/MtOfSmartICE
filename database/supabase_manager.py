"""
Supabase Database Manager for Meituan Crawler
v1.6 - Fixed timeout issues with retry logic and smaller batches
     - Reduced batch size from 100 to 50 for reliability
     - Added exponential backoff retry (3 attempts)
     - Added HTTP timeout configuration (30s)
v1.5 - Optimized save_business_summary with batch upsert (single HTTP request)
     - Previous: 2 HTTP requests per record (GET check + POST/PATCH)
     - Now: 1 HTTP request for ALL records using upsert with on_conflict
v1.4 - Changed mt_business_summary column names to Chinese

Key Features:
- Uploads equity package sales data to Supabase
- Uploads business summary data (综合营业统计) to Supabase
- Gracefully handles unknown stores (logs warning, skips record, continues)
- Error isolation: one failed record won't affect others
- Conditional update: only updates if new values are higher
- Uses anon key by default - no service role key required
- Retry with exponential backoff for network issues

Mapping Strategy:
- equity_package_sales: uses org_code (MD00007) → master_restaurant.meituan_org_code
- business_summary: uses store_name → MEITUAN_STORE_NAME_MAP → master_restaurant.restaurant_name

Usage:
    from database.supabase_manager import SupabaseManager

    manager = SupabaseManager()
    stats = manager.save_equity_package_sales(records)
    stats = manager.save_business_summary(records)
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
import httpx

# Import config for default values
from src.config import SUPABASE_URL as DEFAULT_URL, SUPABASE_KEY as DEFAULT_KEY

# Configure logging
logger = logging.getLogger(__name__)

# Explicit store name mapping: Meituan report name → Supabase restaurant_name
# This is similar to how org_code maps to master_restaurant.meituan_org_code
# Add new mappings here when new stores appear in Meituan reports
MEITUAN_STORE_NAME_MAP = {
    # 宁桂杏 stores
    "宁桂杏山野烤肉（绵阳1958店）": "宁桂杏1958店",
    "宁桂杏山野烤肉（上马店）": "宁桂杏上马店",
    "宁桂杏山野烤肉（常熟世贸店）": "宁桂杏世贸店",
    "宁桂杏山野烤肉（江油首店）": "宁桂杏江油店",
    # 野百灵 stores
    "野百灵·贵州酸汤火锅（1958店）": "野百灵1958店",
    "野百灵·贵州酸汤（绵阳上马店）": "野百灵上马店",
    "野百灵·贵州酸汤火锅（德阳店）": "野百灵同森店",  # 德阳店 = 同森店
}


class SupabaseManager:
    """
    Manages Supabase database operations for Meituan equity package sales data.
    Implements robust error handling to ensure one failed record doesn't block others.
    """

    # Batch and retry configuration
    BATCH_SIZE = 50  # Reduced from 100 for reliability
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2  # seconds
    HTTP_TIMEOUT = 30  # seconds

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

        # Initialize client with extended timeout using SyncClientOptions
        self._client: Client = create_client(
            self.supabase_url,
            self.supabase_key,
            options=SyncClientOptions(
                postgrest_client_timeout=self.HTTP_TIMEOUT,
            )
        )
        logger.info(f"Supabase client initialized for: {self.supabase_url}")

        # Initialize caches
        self._restaurant_cache: Dict[str, str] = {}
        self._restaurant_name_cache: Dict[str, str] = {}
        self._cache_loaded = False

    def _retry_with_backoff(self, operation, batch_num: int, total_batches: int) -> bool:
        """
        Execute an operation with exponential backoff retry.

        Args:
            operation: Callable that performs the database operation
            batch_num: Current batch number (for logging)
            total_batches: Total number of batches (for logging)

        Returns:
            bool: True if successful, False otherwise
        """
        delay = self.INITIAL_RETRY_DELAY

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                operation()
                return True
            except Exception as e:
                error_msg = str(e)
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"Batch {batch_num}/{total_batches} attempt {attempt}/{self.MAX_RETRIES} failed: {error_msg}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Batch {batch_num}/{total_batches} failed after {self.MAX_RETRIES} attempts: {error_msg}")
                    return False

        return False

    def _load_restaurant_cache(self) -> None:
        """
        Load restaurant mappings into cache.
        - meituan_org_code -> restaurant_id (for equity_package_sales)
        - restaurant_name -> restaurant_id (for business_summary)
        Called once on first use to minimize API calls.
        """
        if self._cache_loaded:
            return

        try:
            # Load all restaurants (not just those with org_code)
            result = self._client.table('master_restaurant').select(
                'id, meituan_org_code, restaurant_name'
            ).execute()

            for row in result.data:
                restaurant_id = row['id']
                restaurant_name = row.get('restaurant_name', '')
                org_code = row.get('meituan_org_code')

                # Cache by org_code if available
                if org_code:
                    self._restaurant_cache[org_code] = restaurant_id
                    logger.debug(f"Cached org_code: {org_code} -> {restaurant_id[:8]}...")

                # Cache by restaurant_name (for business_summary lookups)
                if restaurant_name:
                    self._restaurant_name_cache[restaurant_name] = restaurant_id
                    logger.debug(f"Cached name: {restaurant_name} -> {restaurant_id[:8]}...")

            self._cache_loaded = True
            logger.info(
                f"Loaded {len(self._restaurant_cache)} org_code mappings, "
                f"{len(self._restaurant_name_cache)} name mappings from Supabase"
            )

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

    def get_restaurant_id_by_name(self, store_name: str) -> Optional[str]:
        """
        Get restaurant UUID by store name.

        Matching strategy (in order):
        1. Explicit mapping via MEITUAN_STORE_NAME_MAP (preferred, like org_code mapping)
        2. Exact match with master_restaurant.restaurant_name
        3. Fuzzy match as fallback

        Args:
            store_name: Store name from Meituan report (e.g., "宁桂杏山野烤肉（常熟世贸店）")

        Returns:
            Restaurant UUID if found, None otherwise
        """
        self._load_restaurant_cache()

        # Step 1: Try explicit mapping first (like org_code → restaurant_id)
        if store_name in MEITUAN_STORE_NAME_MAP:
            mapped_name = MEITUAN_STORE_NAME_MAP[store_name]
            if mapped_name in self._restaurant_name_cache:
                return self._restaurant_name_cache[mapped_name]

        # Step 2: Try exact match with restaurant_name in cache
        if store_name in self._restaurant_name_cache:
            return self._restaurant_name_cache[store_name]

        # Step 3: Fuzzy match as fallback (for any unmapped stores)
        for cached_name, restaurant_id in self._restaurant_name_cache.items():
            if cached_name in store_name or store_name in cached_name:
                return restaurant_id

        return None

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

    # ==================== Business Summary Methods ====================

    def save_business_summary(
        self,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save business summary records (综合营业统计) to Supabase using batch upsert.

        v1.5 OPTIMIZATION: Single HTTP request for ALL records using upsert()
        - Previous: 2 HTTP requests per record (GET + POST/PATCH) = 1040 requests for 520 records
        - Now: 1 HTTP request total using upsert with on_conflict

        Uses store_name to look up restaurant_id (fuzzy match supported).
        Implements error isolation - unknown stores are skipped gracefully.

        Args:
            records: List of record dictionaries from BusinessSummaryCrawler

        Returns:
            Dictionary with stats: inserted, updated, skipped, failed, unknown_stores
        """
        import json

        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "unknown_stores": []
        }

        if not records:
            logger.warning("No business summary records to save")
            return stats

        # Pre-load restaurant mappings (1 HTTP request)
        self._load_restaurant_cache()

        # Track unique unknown stores
        seen_unknown = set()

        # Phase 1: Transform all records to Supabase format
        valid_records = []
        for record in records:
            store_name = record.get('store_name', '')
            business_date = record.get('business_date', '')

            if not store_name or not business_date:
                logger.warning(f"Missing store_name or business_date: {record}")
                stats["skipped"] += 1
                continue

            # Get restaurant_id by name
            restaurant_id = self.get_restaurant_id_by_name(store_name)

            if not restaurant_id:
                # Unknown store - log warning but continue
                if store_name not in seen_unknown:
                    logger.warning(
                        f"未知门店 (Unknown store): {store_name}. "
                        f"跳过该记录，继续处理其他门店。"
                    )
                    stats["unknown_stores"].append({"store_name": store_name})
                    seen_unknown.add(store_name)
                stats["skipped"] += 1
                continue

            # Transform to Supabase format with Chinese column names
            supabase_record = {
                'restaurant_id': restaurant_id,
                '营业日期': business_date,
                '城市': record.get('city'),
                '门店创建时间': record.get('store_created_at'),
                '营业天数': record.get('operating_days'),
                '营业额': record.get('revenue'),
                '折扣金额': record.get('discount_amount'),
                '营业收入': record.get('business_income'),
                '订单数': record.get('order_count'),
                '就餐人数': record.get('diner_count'),
                '开台数': record.get('table_count'),
                '折前人均': record.get('per_capita_before_discount'),
                '折后人均': record.get('per_capita_after_discount'),
                '折前单均': record.get('avg_order_before_discount'),
                '折后单均': record.get('avg_order_after_discount'),
                '开台率': record.get('table_opening_rate'),
                '翻台率': record.get('table_turnover_rate'),
                '上座率': record.get('occupancy_rate'),
                '平均用餐时长': record.get('avg_dining_time'),
                'updated_at': datetime.utcnow().isoformat()
            }

            # Handle composition_data (JSON)
            composition = record.get('composition_data')
            if composition:
                if isinstance(composition, str):
                    supabase_record['构成数据'] = json.loads(composition)
                else:
                    supabase_record['构成数据'] = composition

            valid_records.append(supabase_record)

        # Phase 2: Batch upsert all valid records with retry logic
        if valid_records:
            total_batches = (len(valid_records) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            logger.info(f"Batch upserting {len(valid_records)} records in {total_batches} batch(es) (batch_size={self.BATCH_SIZE})...")

            for i in range(0, len(valid_records), self.BATCH_SIZE):
                batch = valid_records[i:i + self.BATCH_SIZE]
                batch_num = (i // self.BATCH_SIZE) + 1

                # Define the upsert operation for retry wrapper
                def do_upsert():
                    self._client.table('mt_business_summary').upsert(
                        batch,
                        on_conflict='restaurant_id,营业日期'
                    ).execute()

                # Execute with retry
                success = self._retry_with_backoff(do_upsert, batch_num, total_batches)

                if success:
                    stats["updated"] += len(batch)
                    logger.info(f"Batch {batch_num}/{total_batches}: {len(batch)} records processed")
                else:
                    stats["failed"] += len(batch)

        # Log summary
        total = sum([stats["inserted"], stats["updated"], stats["skipped"], stats["failed"]])
        logger.info(
            f"Supabase business_summary: {total} 条 - "
            f"插入/更新:{stats['updated']} "
            f"跳过:{stats['skipped']} 失败:{stats['failed']}"
        )

        if stats["unknown_stores"]:
            logger.warning(
                f"发现 {len(stats['unknown_stores'])} 个未知门店: "
                f"{[s['store_name'] for s in stats['unknown_stores']]}"
            )

        return stats

    def _get_existing_business_summary(
        self,
        restaurant_id: str,
        business_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing business summary record (using Chinese column name).
        NOTE: Deprecated in v1.5 - batch upsert handles existence check automatically.
        Kept for backwards compatibility.
        """
        try:
            result = self._client.table('mt_business_summary').select(
                'id'
            ).eq(
                'restaurant_id', restaurant_id
            ).eq(
                '营业日期', business_date
            ).execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"查询现有记录失败: {e}")
            return None

    def _insert_business_summary(self, restaurant_id: str, record: Dict[str, Any]) -> None:
        """
        Insert a new business summary record (using Chinese column names).
        NOTE: Deprecated in v1.5 - use save_business_summary() with batch upsert instead.
        Kept for backwards compatibility.
        """
        import json

        data = {
            'restaurant_id': restaurant_id,
            '营业日期': record.get('business_date'),
            '城市': record.get('city'),
            '门店创建时间': record.get('store_created_at'),
            '营业天数': record.get('operating_days'),
            '营业额': record.get('revenue'),
            '折扣金额': record.get('discount_amount'),
            '营业收入': record.get('business_income'),
            '订单数': record.get('order_count'),
            '就餐人数': record.get('diner_count'),
            '开台数': record.get('table_count'),
            '折前人均': record.get('per_capita_before_discount'),
            '折后人均': record.get('per_capita_after_discount'),
            '折前单均': record.get('avg_order_before_discount'),
            '折后单均': record.get('avg_order_after_discount'),
            '开台率': record.get('table_opening_rate'),
            '翻台率': record.get('table_turnover_rate'),
            '上座率': record.get('occupancy_rate'),
            '平均用餐时长': record.get('avg_dining_time'),
        }

        # Handle composition_data (already JSON string from crawler)
        composition = record.get('composition_data')
        if composition:
            # Parse and re-serialize to ensure valid JSON for Supabase JSONB
            if isinstance(composition, str):
                data['构成数据'] = json.loads(composition)
            else:
                data['构成数据'] = composition

        self._client.table('mt_business_summary').insert(data).execute()

    def _update_business_summary(self, record_id: str, record: Dict[str, Any]) -> None:
        """
        Update an existing business summary record (using Chinese column names).
        NOTE: Deprecated in v1.5 - use save_business_summary() with batch upsert instead.
        Kept for backwards compatibility.
        """
        import json

        data = {
            '城市': record.get('city'),
            '门店创建时间': record.get('store_created_at'),
            '营业天数': record.get('operating_days'),
            '营业额': record.get('revenue'),
            '折扣金额': record.get('discount_amount'),
            '营业收入': record.get('business_income'),
            '订单数': record.get('order_count'),
            '就餐人数': record.get('diner_count'),
            '开台数': record.get('table_count'),
            '折前人均': record.get('per_capita_before_discount'),
            '折后人均': record.get('per_capita_after_discount'),
            '折前单均': record.get('avg_order_before_discount'),
            '折后单均': record.get('avg_order_after_discount'),
            '开台率': record.get('table_opening_rate'),
            '翻台率': record.get('table_turnover_rate'),
            '上座率': record.get('occupancy_rate'),
            '平均用餐时长': record.get('avg_dining_time'),
            'updated_at': datetime.utcnow().isoformat()
        }

        # Handle composition_data
        composition = record.get('composition_data')
        if composition:
            if isinstance(composition, str):
                data['构成数据'] = json.loads(composition)
            else:
                data['构成数据'] = composition

        self._client.table('mt_business_summary').update(data).eq('id', record_id).execute()

    # ==================== Equity Sales Query Methods ====================

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
        self._restaurant_name_cache.clear()
        self._load_restaurant_cache()
        logger.info(
            f"Restaurant cache refreshed: {len(self._restaurant_cache)} org_code, "
            f"{len(self._restaurant_name_cache)} name mappings"
        )

    def save_dish_sales(
        self,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save dish sales records (菜品综合统计) to Supabase using batch upsert.

        Uses store_name to look up restaurant_id (fuzzy match supported).
        Implements error isolation - unknown stores are skipped gracefully.

        Args:
            records: List of record dictionaries from DishSalesCrawler

        Returns:
            Dictionary with stats: inserted, updated, skipped, failed, unknown_stores
        """
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "unknown_stores": []
        }

        if not records:
            logger.warning("No dish sales records to save")
            return stats

        # Pre-load restaurant mappings (1 HTTP request)
        self._load_restaurant_cache()

        # Track unique unknown stores
        seen_unknown = set()

        # Phase 1: Transform all records to Supabase format
        valid_records = []
        for record in records:
            store_name = record.get('store_name', '')
            business_date = record.get('business_date', '')
            dish_name = record.get('dish_name', '')

            if not store_name or not business_date or not dish_name:
                logger.warning(f"Missing required fields: {record}")
                stats["skipped"] += 1
                continue

            # Get restaurant_id by name
            restaurant_id = self.get_restaurant_id_by_name(store_name)

            if not restaurant_id:
                # Unknown store - log warning but continue
                if store_name not in seen_unknown:
                    logger.warning(
                        f"未知门店 (Unknown store): {store_name}. "
                        f"跳过该记录，继续处理其他门店。"
                    )
                    stats["unknown_stores"].append({"store_name": store_name})
                    seen_unknown.add(store_name)
                stats["skipped"] += 1
                continue

            # Transform to Supabase format (using Chinese column names)
            supabase_record = {
                'restaurant_id': restaurant_id,
                '营业日期': business_date,
                '菜品名称': dish_name,
                '销售数量': record.get('sales_quantity'),
                '销售数量占比': record.get('sales_quantity_pct'),
                '折前均价': record.get('price_before_discount'),
                '折后均价': record.get('price_after_discount'),
                '销售额': record.get('sales_amount'),
                '销售额占比': record.get('sales_amount_pct'),
                '优惠金额': record.get('discount_amount'),
                '菜品优惠占比': record.get('dish_discount_pct'),
                '菜品收入': record.get('dish_income'),
                '菜品收入占比': record.get('dish_income_pct'),
                '点菜数量': record.get('order_quantity'),
                '点菜金额': record.get('order_amount'),
                '退菜数量': record.get('return_quantity'),
                '退菜金额': record.get('return_amount'),
                '退菜数量占比': record.get('return_quantity_pct'),
                '退菜金额占比': record.get('return_amount_pct'),
                '退菜率': record.get('return_rate'),
                '退菜订单量': record.get('return_order_count'),
                '赠菜数量': record.get('gift_quantity'),
                '赠菜金额': record.get('gift_amount'),
                '赠菜数量占比': record.get('gift_quantity_pct'),
                '赠菜金额占比': record.get('gift_amount_pct'),
                '菜品销售订单量': record.get('dish_order_count'),
                '关联订单金额': record.get('related_order_amount'),
                '菜品销售千次': record.get('sales_per_thousand'),
                '菜品点单率': record.get('order_rate'),
                '顾客点击率': record.get('customer_click_rate'),
                'updated_at': datetime.utcnow().isoformat()
            }

            valid_records.append(supabase_record)

        # Phase 2: Batch upsert all valid records with retry logic
        if valid_records:
            total_batches = (len(valid_records) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            logger.info(f"Batch upserting {len(valid_records)} records in {total_batches} batch(es) (batch_size={self.BATCH_SIZE})...")

            for i in range(0, len(valid_records), self.BATCH_SIZE):
                batch = valid_records[i:i + self.BATCH_SIZE]
                batch_num = (i // self.BATCH_SIZE) + 1

                # Define the upsert operation for retry wrapper
                def do_upsert():
                    self._client.table('mt_dish_sales').upsert(
                        batch,
                        on_conflict='restaurant_id,营业日期,菜品名称'
                    ).execute()

                # Execute with retry
                success = self._retry_with_backoff(do_upsert, batch_num, total_batches)

                if success:
                    stats["updated"] += len(batch)
                    logger.info(f"Batch {batch_num}/{total_batches}: {len(batch)} records processed")
                else:
                    stats["failed"] += len(batch)

        # Log summary
        total = sum([stats["inserted"], stats["updated"], stats["skipped"], stats["failed"]])
        logger.info(
            f"Supabase dish_sales: {total} 条 - "
            f"插入/更新:{stats['updated']} "
            f"跳过:{stats['skipped']} 失败:{stats['failed']}"
        )

        if stats["unknown_stores"]:
            logger.warning(
                f"发现 {len(stats['unknown_stores'])} 个未知门店: "
                f"{[s['store_name'] for s in stats['unknown_stores']]}"
            )

        return stats


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
