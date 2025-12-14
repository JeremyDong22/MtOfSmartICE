"""
Database Manager for Meituan Merchant Backend Crawler
Handles all database operations including store management, data storage, and reporting.
"""

import sqlite3
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date
from contextlib import contextmanager
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for Meituan crawler data.
    Provides thread-safe operations for storing and querying merchant data.
    """

    # Database schema version for migrations
    SCHEMA_VERSION = 1

    # Default stores to populate
    DEFAULT_STORES = [
        {
            "merchant_id": "56756952",
            "store_name": "宁桂杏山野烤肉（绵阳1958店）",
            "org_code": "MD00006"
        },
        {
            "merchant_id": "56728236",
            "store_name": "宁桂杏山野烤肉（常熟世贸店）",
            "org_code": "MD00007"
        },
        {
            "merchant_id": "56799302",
            "store_name": "野百灵·贵州酸汤火锅（1958店）",
            "org_code": "MD00008"
        },
        {
            "merchant_id": "58188193",
            "store_name": "宁桂杏山野烤肉（上马店）",
            "org_code": "MD00009"
        },
        {
            "merchant_id": "58121229",
            "store_name": "野百灵·贵州酸汤火锅（德阳店）",
            "org_code": "MD00010"
        },
        {
            "merchant_id": "58325928",
            "store_name": "宁桂杏山野烤肉（江油首店）",
            "org_code": "MD00011"
        }
    ]

    def __init__(self, db_path: str = "database/meituan_data.db"):
        """
        Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._lock = Lock()  # Thread safety lock

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()
        logger.info(f"Database initialized at: {self.db_path}")

    def _init_db(self):
        """Initialize database and create tables if they don't exist."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Create stores table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stores (
                        merchant_id TEXT PRIMARY KEY,
                        store_name TEXT NOT NULL,
                        org_code TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create membership card data table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS membership_card_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        merchant_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        cards_opened INTEGER DEFAULT 0,
                        total_amount REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (merchant_id) REFERENCES stores(merchant_id),
                        UNIQUE(merchant_id, date)
                    )
                """)

                # Create card details table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS card_details (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        membership_data_id INTEGER NOT NULL,
                        card_id TEXT,
                        amount REAL NOT NULL,
                        card_type TEXT,
                        transaction_time TIMESTAMP,
                        FOREIGN KEY (membership_data_id) REFERENCES membership_card_data(id)
                    )
                """)

                # Create crawl log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crawl_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        merchant_id TEXT NOT NULL,
                        crawler_type TEXT NOT NULL,
                        date TEXT NOT NULL,
                        status TEXT NOT NULL,
                        records_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (merchant_id) REFERENCES stores(merchant_id),
                        UNIQUE(merchant_id, crawler_type, date)
                    )
                """)

                # Create metadata table for migrations
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Set schema version
                cursor.execute("""
                    INSERT OR REPLACE INTO metadata (key, value)
                    VALUES ('schema_version', ?)
                """, (str(self.SCHEMA_VERSION),))

                # Create indexes for better query performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_membership_merchant_date
                    ON membership_card_data(merchant_id, date)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_crawl_log_merchant_type_date
                    ON crawl_log(merchant_id, crawler_type, date)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_card_details_membership_id
                    ON card_details(membership_data_id)
                """)

                # Populate default stores (done in same transaction)
                for store in self.DEFAULT_STORES:
                    cursor.execute("""
                        INSERT OR IGNORE INTO stores (merchant_id, store_name, org_code)
                        VALUES (?, ?, ?)
                    """, (
                        store["merchant_id"],
                        store["store_name"],
                        store["org_code"]
                    ))

                conn.commit()
                logger.info("Database tables created successfully")
                logger.info(f"Populated {len(self.DEFAULT_STORES)} default stores")

        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Provides thread-safe database access.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = None
        try:
            with self._lock:
                conn = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row  # Enable column access by name
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys = ON")
                yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # ==================== Store Operations ====================

    def populate_default_stores(self):
        """
        Populate stores table with default stores.
        Safe to call multiple times (uses INSERT OR IGNORE).
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                for store in self.DEFAULT_STORES:
                    cursor.execute("""
                        INSERT OR IGNORE INTO stores (merchant_id, store_name, org_code)
                        VALUES (?, ?, ?)
                    """, (
                        store["merchant_id"],
                        store["store_name"],
                        store["org_code"]
                    ))

                conn.commit()
                logger.info(f"Populated {len(self.DEFAULT_STORES)} default stores")

        except sqlite3.Error as e:
            logger.error(f"Error populating stores: {e}")
            raise

    def get_all_stores(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stores from the database.

        Returns:
            List of store dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT merchant_id, store_name, org_code, created_at, updated_at
                    FROM stores
                    ORDER BY org_code
                """)

                stores = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(stores)} stores")
                return stores

        except sqlite3.Error as e:
            logger.error(f"Error retrieving stores: {e}")
            return []

    def get_store(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get store information by merchant ID.

        Args:
            merchant_id: The merchant/store ID

        Returns:
            Store dictionary or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT merchant_id, store_name, org_code, created_at, updated_at
                    FROM stores
                    WHERE merchant_id = ?
                """, (merchant_id,))

                row = cursor.fetchone()
                if row:
                    return dict(row)
                else:
                    logger.warning(f"Store not found: {merchant_id}")
                    return None

        except sqlite3.Error as e:
            logger.error(f"Error retrieving store {merchant_id}: {e}")
            return None

    def add_store(
        self,
        merchant_id: str,
        store_name: str,
        org_code: Optional[str] = None
    ) -> bool:
        """
        Add a new store to the database.

        Args:
            merchant_id: The merchant/store ID
            store_name: Name of the store
            org_code: Optional organization code

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO stores (merchant_id, store_name, org_code, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (merchant_id, store_name, org_code))

                conn.commit()
                logger.info(f"Added/updated store: {store_name} ({merchant_id})")
                return True

        except sqlite3.Error as e:
            logger.error(f"Error adding store {merchant_id}: {e}")
            return False

    # ==================== Membership Card Data Operations ====================

    def save_membership_data(
        self,
        store_id: str,
        store_name: str,
        date: str,
        cards_opened: int,
        total_amount: float,
        card_details: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Save membership card data for a store on a specific date.
        Uses UPSERT to update existing records.

        Args:
            store_id: The merchant/store ID
            store_name: Name of the store
            date: Date in YYYY-MM-DD format
            cards_opened: Number of cards opened
            total_amount: Total amount of card sales
            card_details: Optional list of individual card transaction details

        Returns:
            The ID of the inserted/updated record, or -1 on error
        """
        # Validate date format
        if not self._validate_date(date):
            logger.error(f"Invalid date format: {date}. Expected YYYY-MM-DD")
            return -1

        # Validate amounts
        if cards_opened < 0 or total_amount < 0:
            logger.error("Cards opened and total amount must be non-negative")
            return -1

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure store exists (inline to avoid nested connection)
                cursor.execute("""
                    INSERT OR REPLACE INTO stores (merchant_id, store_name, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (store_id, store_name))

                # Insert or update membership data
                cursor.execute("""
                    INSERT INTO membership_card_data
                    (merchant_id, date, cards_opened, total_amount)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(merchant_id, date)
                    DO UPDATE SET
                        cards_opened = excluded.cards_opened,
                        total_amount = excluded.total_amount,
                        created_at = CURRENT_TIMESTAMP
                """, (store_id, date, cards_opened, total_amount))

                # Get the ID of the inserted/updated record
                membership_data_id = cursor.lastrowid
                if membership_data_id == 0:
                    # Record was updated, get its ID
                    cursor.execute("""
                        SELECT id FROM membership_card_data
                        WHERE merchant_id = ? AND date = ?
                    """, (store_id, date))
                    row = cursor.fetchone()
                    if row:
                        membership_data_id = row[0]

                # Save card details if provided
                if card_details and membership_data_id > 0:
                    # Delete existing card details for this record
                    cursor.execute("""
                        DELETE FROM card_details
                        WHERE membership_data_id = ?
                    """, (membership_data_id,))

                    # Insert new card details
                    for detail in card_details:
                        cursor.execute("""
                            INSERT INTO card_details
                            (membership_data_id, card_id, amount, card_type, transaction_time)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            membership_data_id,
                            detail.get('card_id'),
                            detail.get('amount', 0.0),
                            detail.get('card_type'),
                            detail.get('transaction_time')
                        ))

                    logger.info(f"Saved {len(card_details)} card details")

                conn.commit()
                logger.info(
                    f"Saved membership data for {store_name} on {date}: "
                    f"{cards_opened} cards, {total_amount:.2f} yuan"
                )
                return membership_data_id

        except sqlite3.Error as e:
            logger.error(f"Error saving membership data: {e}")
            return -1

    def get_membership_data(
        self,
        store_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query membership data with optional filters.

        Args:
            store_id: Filter by merchant/store ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)

        Returns:
            List of membership data records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT
                        m.id,
                        m.merchant_id,
                        s.store_name,
                        s.org_code,
                        m.date,
                        m.cards_opened,
                        m.total_amount,
                        m.created_at
                    FROM membership_card_data m
                    JOIN stores s ON m.merchant_id = s.merchant_id
                    WHERE 1=1
                """
                params = []

                if store_id:
                    query += " AND m.merchant_id = ?"
                    params.append(store_id)

                if start_date:
                    query += " AND m.date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND m.date <= ?"
                    params.append(end_date)

                query += " ORDER BY m.date DESC, s.store_name"

                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"Retrieved {len(results)} membership data records")
                return results

        except sqlite3.Error as e:
            logger.error(f"Error retrieving membership data: {e}")
            return []

    def get_card_details(self, membership_data_id: int) -> List[Dict[str, Any]]:
        """
        Get card details for a specific membership data record.

        Args:
            membership_data_id: The ID of the membership data record

        Returns:
            List of card detail records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        id,
                        membership_data_id,
                        card_id,
                        amount,
                        card_type,
                        transaction_time
                    FROM card_details
                    WHERE membership_data_id = ?
                    ORDER BY transaction_time DESC
                """, (membership_data_id,))

                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(results)} card details")
                return results

        except sqlite3.Error as e:
            logger.error(f"Error retrieving card details: {e}")
            return []

    # ==================== Crawl Tracking Operations ====================

    def data_exists(
        self,
        store_id: str,
        date: str,
        crawler_type: str
    ) -> bool:
        """
        Check if data has already been crawled for a store/date/type.

        Args:
            store_id: The merchant/store ID
            date: Date in YYYY-MM-DD format
            crawler_type: Type of crawler (e.g., "membership_card")

        Returns:
            True if data exists and was successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM crawl_log
                    WHERE merchant_id = ?
                        AND date = ?
                        AND crawler_type = ?
                        AND status = 'success'
                """, (store_id, date, crawler_type))

                row = cursor.fetchone()
                exists = row['count'] > 0

                if exists:
                    logger.info(
                        f"Data already exists for {store_id} on {date} ({crawler_type})"
                    )

                return exists

        except sqlite3.Error as e:
            logger.error(f"Error checking data existence: {e}")
            return False

    def log_crawl(
        self,
        store_id: str,
        crawler_type: str,
        date: str,
        status: str,
        records_count: int = 0,
        error_message: Optional[str] = None
    ):
        """
        Log a crawl operation.

        Args:
            store_id: The merchant/store ID
            crawler_type: Type of crawler
            date: Date in YYYY-MM-DD format
            status: Status ('success', 'failed', 'partial')
            records_count: Number of records crawled
            error_message: Optional error message if failed
        """
        # Validate status
        valid_statuses = ['success', 'failed', 'partial']
        if status not in valid_statuses:
            logger.warning(
                f"Invalid status '{status}'. Using 'failed'. "
                f"Valid: {valid_statuses}"
            )
            status = 'failed'

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO crawl_log
                    (merchant_id, crawler_type, date, status, records_count, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(merchant_id, crawler_type, date)
                    DO UPDATE SET
                        status = excluded.status,
                        records_count = excluded.records_count,
                        error_message = excluded.error_message,
                        crawled_at = CURRENT_TIMESTAMP
                """, (
                    store_id,
                    crawler_type,
                    date,
                    status,
                    records_count,
                    error_message
                ))

                conn.commit()
                logger.info(
                    f"Logged crawl for {store_id} on {date} ({crawler_type}): "
                    f"{status} - {records_count} records"
                )

        except sqlite3.Error as e:
            logger.error(f"Error logging crawl: {e}")

    def get_crawl_status(
        self,
        store_id: Optional[str] = None,
        crawler_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get crawl status/history with optional filters.

        Args:
            store_id: Filter by merchant/store ID
            crawler_type: Filter by crawler type

        Returns:
            List of crawl log records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        c.id,
                        c.merchant_id,
                        s.store_name,
                        c.crawler_type,
                        c.date,
                        c.status,
                        c.records_count,
                        c.error_message,
                        c.crawled_at
                    FROM crawl_log c
                    JOIN stores s ON c.merchant_id = s.merchant_id
                    WHERE 1=1
                """
                params = []

                if store_id:
                    query += " AND c.merchant_id = ?"
                    params.append(store_id)

                if crawler_type:
                    query += " AND c.crawler_type = ?"
                    params.append(crawler_type)

                query += " ORDER BY c.crawled_at DESC"

                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"Retrieved {len(results)} crawl log records")
                return results

        except sqlite3.Error as e:
            logger.error(f"Error retrieving crawl status: {e}")
            return []

    # ==================== Reporting and Analytics ====================

    def get_daily_summary(
        self,
        store_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get daily summary of membership card data.

        Args:
            store_id: Filter by merchant/store ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)

        Returns:
            List of daily summary records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        m.date,
                        COUNT(DISTINCT m.merchant_id) as store_count,
                        SUM(m.cards_opened) as total_cards,
                        SUM(m.total_amount) as total_amount,
                        AVG(m.total_amount) as avg_amount_per_store
                    FROM membership_card_data m
                    WHERE 1=1
                """
                params = []

                if store_id:
                    query += " AND m.merchant_id = ?"
                    params.append(store_id)

                if start_date:
                    query += " AND m.date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND m.date <= ?"
                    params.append(end_date)

                query += " GROUP BY m.date ORDER BY m.date DESC"

                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"Retrieved {len(results)} daily summary records")
                return results

        except sqlite3.Error as e:
            logger.error(f"Error retrieving daily summary: {e}")
            return []

    def get_store_totals(self) -> List[Dict[str, Any]]:
        """
        Get total cards and amount per store across all dates.

        Returns:
            List of store totals
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        s.merchant_id,
                        s.store_name,
                        s.org_code,
                        COUNT(m.id) as days_with_data,
                        SUM(m.cards_opened) as total_cards,
                        SUM(m.total_amount) as total_amount,
                        AVG(m.cards_opened) as avg_cards_per_day,
                        AVG(m.total_amount) as avg_amount_per_day,
                        MIN(m.date) as first_date,
                        MAX(m.date) as last_date
                    FROM stores s
                    LEFT JOIN membership_card_data m ON s.merchant_id = m.merchant_id
                    GROUP BY s.merchant_id, s.store_name, s.org_code
                    ORDER BY s.org_code
                """)

                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Retrieved totals for {len(results)} stores")
                return results

        except sqlite3.Error as e:
            logger.error(f"Error retrieving store totals: {e}")
            return []

    # ==================== Data Export ====================

    def export_to_csv(
        self,
        output_path: str,
        store_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """
        Export membership data to CSV file.

        Args:
            output_path: Path to save the CSV file
            store_id: Filter by merchant/store ID
            start_date: Filter by start date
            end_date: Filter by end date
        """
        try:
            # Get data
            data = self.get_membership_data(store_id, start_date, end_date)

            if not data:
                logger.warning("No data to export")
                return

            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'merchant_id', 'store_name', 'org_code', 'date',
                    'cards_opened', 'total_amount', 'created_at'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for row in data:
                    # Filter to only include specified fields
                    filtered_row = {k: row.get(k) for k in fieldnames}
                    writer.writerow(filtered_row)

            logger.info(f"Exported {len(data)} records to CSV: {output_path}")

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")

    def export_to_json(
        self,
        output_path: str,
        store_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Export membership data to JSON file.

        Args:
            output_path: Path to save the JSON file
            store_id: Filter by merchant/store ID
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Path to the created JSON file
        """
        try:
            # Get data
            data = self.get_membership_data(store_id, start_date, end_date)

            if not data:
                logger.warning("No data to export")
                return ""

            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare export structure
            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "record_count": len(data),
                    "filters": {
                        "store_id": store_id,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                },
                "data": data
            }

            # Write to JSON
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported {len(data)} records to JSON: {output_path}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return ""

    def export_store_summary(self, output_path: str):
        """
        Export store totals summary to CSV.

        Args:
            output_path: Path to save the CSV file
        """
        try:
            # Get store totals
            data = self.get_store_totals()

            if not data:
                logger.warning("No data to export")
                return

            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'merchant_id', 'store_name', 'org_code', 'days_with_data',
                    'total_cards', 'total_amount', 'avg_cards_per_day',
                    'avg_amount_per_day', 'first_date', 'last_date'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"Exported store summary to CSV: {output_path}")

        except Exception as e:
            logger.error(f"Error exporting store summary: {e}")

    # ==================== Utility Methods ====================

    def _validate_date(self, date_string: str) -> bool:
        """
        Validate date string format (YYYY-MM-DD).

        Args:
            date_string: Date string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            datetime.strptime(date_string, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def get_schema_version(self) -> int:
        """
        Get the current database schema version.

        Returns:
            Schema version number
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM metadata WHERE key = 'schema_version'
                """)
                row = cursor.fetchone()
                if row:
                    return int(row['value'])
                return 0
        except sqlite3.Error:
            return 0

    def vacuum(self):
        """
        Optimize the database by running VACUUM.
        This reclaims unused space and optimizes the database file.
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
        except sqlite3.Error as e:
            logger.error(f"Error vacuuming database: {e}")

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                stats = {}

                # Get table counts
                cursor.execute("SELECT COUNT(*) as count FROM stores")
                stats['stores_count'] = cursor.fetchone()['count']

                cursor.execute("SELECT COUNT(*) as count FROM membership_card_data")
                stats['membership_records'] = cursor.fetchone()['count']

                cursor.execute("SELECT COUNT(*) as count FROM card_details")
                stats['card_details_count'] = cursor.fetchone()['count']

                cursor.execute("SELECT COUNT(*) as count FROM crawl_log")
                stats['crawl_log_count'] = cursor.fetchone()['count']

                # Get date range
                cursor.execute("""
                    SELECT MIN(date) as min_date, MAX(date) as max_date
                    FROM membership_card_data
                """)
                row = cursor.fetchone()
                stats['data_date_range'] = {
                    'start': row['min_date'],
                    'end': row['max_date']
                }

                # Get database file size
                stats['database_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
                stats['database_path'] = str(self.db_path)

                return stats

        except sqlite3.Error as e:
            logger.error(f"Error getting database stats: {e}")
            return {}


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the DatabaseManager class.
    """

    # Initialize database
    db = DatabaseManager()

    print("\n=== Database Initialized ===")
    print(f"Database location: {db.db_path}")

    # Display all stores
    print("\n=== All Stores ===")
    stores = db.get_all_stores()
    for store in stores:
        print(f"- {store['store_name']} (ID: {store['merchant_id']}, Code: {store['org_code']})")

    # Example: Save some test data
    print("\n=== Saving Test Data ===")
    test_date = "2024-01-15"
    test_store_id = "56756952"

    if not db.data_exists(test_store_id, test_date, "membership_card"):
        # Save membership data
        membership_id = db.save_membership_data(
            store_id=test_store_id,
            store_name="宁桂杏山野烤肉（绵阳1958店）",
            date=test_date,
            cards_opened=5,
            total_amount=1500.00,
            card_details=[
                {
                    "card_id": "MC001",
                    "amount": 300.00,
                    "card_type": "山海会员",
                    "transaction_time": "2024-01-15 10:30:00"
                },
                {
                    "card_id": "MC002",
                    "amount": 500.00,
                    "card_type": "山海会员",
                    "transaction_time": "2024-01-15 14:20:00"
                },
                {
                    "card_id": "MC003",
                    "amount": 200.00,
                    "card_type": "基础会员",
                    "transaction_time": "2024-01-15 16:45:00"
                },
                {
                    "card_id": "MC004",
                    "amount": 300.00,
                    "card_type": "山海会员",
                    "transaction_time": "2024-01-15 18:10:00"
                },
                {
                    "card_id": "MC005",
                    "amount": 200.00,
                    "card_type": "基础会员",
                    "transaction_time": "2024-01-15 19:30:00"
                }
            ]
        )

        print(f"Saved membership data with ID: {membership_id}")

        # Log the crawl
        db.log_crawl(
            store_id=test_store_id,
            crawler_type="membership_card",
            date=test_date,
            status="success",
            records_count=5
        )
        print("Logged crawl operation")
    else:
        print(f"Data already exists for {test_store_id} on {test_date}")

    # Query data
    print("\n=== Querying Data ===")
    membership_data = db.get_membership_data(store_id=test_store_id)
    print(f"Found {len(membership_data)} membership records")
    for record in membership_data:
        print(f"  {record['date']}: {record['cards_opened']} cards, {record['total_amount']:.2f} yuan")

    # Get daily summary
    print("\n=== Daily Summary ===")
    summary = db.get_daily_summary()
    for day in summary:
        print(f"{day['date']}: {day['total_cards']} cards, {day['total_amount']:.2f} yuan")

    # Get store totals
    print("\n=== Store Totals ===")
    totals = db.get_store_totals()
    for store_total in totals:
        if store_total['total_cards']:
            print(
                f"{store_total['store_name']}: "
                f"{store_total['total_cards']} cards, "
                f"{store_total['total_amount']:.2f} yuan "
                f"(avg {store_total['avg_cards_per_day']:.1f} cards/day)"
            )

    # Database statistics
    print("\n=== Database Statistics ===")
    stats = db.get_database_stats()
    print(f"Stores: {stats['stores_count']}")
    print(f"Membership records: {stats['membership_records']}")
    print(f"Card details: {stats['card_details_count']}")
    print(f"Crawl logs: {stats['crawl_log_count']}")
    print(f"Date range: {stats['data_date_range']['start']} to {stats['data_date_range']['end']}")
    print(f"Database size: {stats['database_size_mb']:.2f} MB")

    # Export examples
    print("\n=== Export Examples ===")
    db.export_to_csv("reports/membership_data.csv")
    db.export_to_json("reports/membership_data.json")
    db.export_store_summary("reports/store_summary.csv")
    print("Exports completed")
