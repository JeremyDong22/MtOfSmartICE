"""
Database Manager for Meituan Crawler - Simplified version for equity package sales
v2.1 - Added conditional duplicate handling: only updates if new values are higher
       Added updated_at column to track when records change
       Compatible with both SQLite and PostgreSQL (Supabase)

Tables:
- mt_stores: Store information with org_code as primary key
- mt_equity_package_sales: Equity package sales data linked to stores

Duplicate Handling Logic:
- If record exists for (org_code, date, package_name), compare values
- Only update if new quantity_sold > existing OR new total_sales > existing
- This handles mid-day vs end-of-day data collection scenarios
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
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
    Manages SQLite database operations for Meituan equity package sales data.
    Provides thread-safe operations for storing and querying data.
    """

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

                # Create stores table - org_code is primary key
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mt_stores (
                        org_code TEXT PRIMARY KEY,
                        store_name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create equity package sales table with updated_at for tracking changes
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mt_equity_package_sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        org_code TEXT NOT NULL,
                        date TEXT NOT NULL,
                        package_name TEXT NOT NULL,
                        unit_price REAL NOT NULL,
                        quantity_sold INTEGER NOT NULL,
                        total_sales REAL NOT NULL,
                        refund_quantity INTEGER DEFAULT 0,
                        refund_amount REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (org_code) REFERENCES mt_stores(org_code),
                        UNIQUE(org_code, date, package_name)
                    )
                """)

                # Add updated_at column if table exists but column doesn't (migration)
                try:
                    cursor.execute("""
                        ALTER TABLE mt_equity_package_sales
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    logger.info("Added updated_at column to mt_equity_package_sales")
                except sqlite3.OperationalError:
                    pass  # Column already exists

                # Create indexes for better query performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_equity_sales_org_date
                    ON mt_equity_package_sales(org_code, date)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_equity_sales_date
                    ON mt_equity_package_sales(date)
                """)

                conn.commit()
                logger.info("Database tables created successfully")

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

    def save_store(self, org_code: str, store_name: str) -> bool:
        """
        Save or update a store. Uses UPSERT pattern.

        Args:
            org_code: Organization code (e.g., "MD00007")
            store_name: Store name

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mt_stores (org_code, store_name)
                    VALUES (?, ?)
                    ON CONFLICT(org_code)
                    DO UPDATE SET
                        store_name = excluded.store_name,
                        updated_at = CURRENT_TIMESTAMP
                """, (org_code, store_name))

                conn.commit()
                logger.info(f"Saved store: {store_name} ({org_code})")
                return True

        except sqlite3.Error as e:
            logger.error(f"Error saving store {org_code}: {e}")
            return False

    def get_stores(self) -> List[Dict[str, Any]]:
        """
        Get all stores from the database.

        Returns:
            List of store dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT org_code, store_name, created_at, updated_at
                    FROM mt_stores
                    ORDER BY org_code
                """)

                stores = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(stores)} stores")
                return stores

        except sqlite3.Error as e:
            logger.error(f"Error retrieving stores: {e}")
            return []

    # ==================== Equity Package Sales Operations ====================

    def save_equity_package_sales(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Save equity package sales records with conditional duplicate handling.
        Only updates existing records if new values are higher (quantity_sold or total_sales).
        Automatically creates stores if they don't exist.

        Duplicate Logic:
        - If record doesn't exist: INSERT new record
        - If record exists AND (new quantity > old OR new sales > old): UPDATE record
        - If record exists AND new values are NOT higher: SKIP (keep existing)

        This handles the scenario where mid-day crawls have lower values than end-of-day.

        Args:
            records: List of record dictionaries with keys:
                - org_code: Organization code
                - store_name: Store name
                - date: Date in YYYY-MM-DD format
                - package_name: Package name
                - unit_price: Unit price
                - quantity_sold: Quantity sold
                - total_sales: Total sales amount
                - refund_quantity: Refund quantity (optional)
                - refund_amount: Refund amount (optional)

        Returns:
            Dictionary with counts: {"inserted": N, "updated": N, "skipped": N}
        """
        stats = {"inserted": 0, "updated": 0, "skipped": 0}

        if not records:
            logger.warning("No records to save")
            return stats

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                for record in records:
                    org_code = record['org_code']
                    store_name = record['store_name']
                    date = record['date']
                    package_name = record['package_name']
                    new_quantity = record['quantity_sold']
                    new_sales = record['total_sales']

                    # Ensure store exists first
                    cursor.execute("""
                        INSERT INTO mt_stores (org_code, store_name)
                        VALUES (?, ?)
                        ON CONFLICT(org_code)
                        DO UPDATE SET
                            store_name = excluded.store_name,
                            updated_at = CURRENT_TIMESTAMP
                    """, (org_code, store_name))

                    # Check if record exists and get current values
                    cursor.execute("""
                        SELECT id, quantity_sold, total_sales
                        FROM mt_equity_package_sales
                        WHERE org_code = ? AND date = ? AND package_name = ?
                    """, (org_code, date, package_name))

                    existing = cursor.fetchone()

                    if existing is None:
                        # No existing record - INSERT new
                        cursor.execute("""
                            INSERT INTO mt_equity_package_sales
                            (org_code, date, package_name, unit_price, quantity_sold,
                             total_sales, refund_quantity, refund_amount, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (
                            org_code, date, package_name,
                            record['unit_price'], new_quantity, new_sales,
                            record.get('refund_quantity', 0),
                            record.get('refund_amount', 0.0)
                        ))
                        stats["inserted"] += 1
                        logger.debug(f"INSERT: {org_code}/{date}/{package_name} - qty={new_quantity}, sales={new_sales}")

                    else:
                        # Record exists - check if new values are higher
                        old_quantity = existing['quantity_sold']
                        old_sales = existing['total_sales']

                        if new_quantity > old_quantity or new_sales > old_sales:
                            # New values are higher - UPDATE
                            cursor.execute("""
                                UPDATE mt_equity_package_sales
                                SET unit_price = ?,
                                    quantity_sold = ?,
                                    total_sales = ?,
                                    refund_quantity = ?,
                                    refund_amount = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (
                                record['unit_price'], new_quantity, new_sales,
                                record.get('refund_quantity', 0),
                                record.get('refund_amount', 0.0),
                                existing['id']
                            ))
                            stats["updated"] += 1
                            logger.debug(
                                f"UPDATE: {org_code}/{date}/{package_name} - "
                                f"qty: {old_quantity}->{new_quantity}, sales: {old_sales}->{new_sales}"
                            )

                        else:
                            # New values are NOT higher - SKIP
                            stats["skipped"] += 1
                            logger.debug(
                                f"SKIP: {org_code}/{date}/{package_name} - "
                                f"existing qty={old_quantity} >= new qty={new_quantity}, "
                                f"existing sales={old_sales} >= new sales={new_sales}"
                            )

                conn.commit()

                total = stats["inserted"] + stats["updated"] + stats["skipped"]
                logger.info(
                    f"Processed {total} records: "
                    f"{stats['inserted']} inserted, {stats['updated']} updated, {stats['skipped']} skipped"
                )
                return stats

        except sqlite3.Error as e:
            logger.error(f"Error saving equity package sales: {e}")
            return stats

    def get_equity_sales(
        self,
        org_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query equity package sales with optional filters.

        Args:
            org_code: Filter by organization code
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)

        Returns:
            List of sales records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT
                        s.id,
                        s.org_code,
                        st.store_name,
                        s.date,
                        s.package_name,
                        s.unit_price,
                        s.quantity_sold,
                        s.total_sales,
                        s.refund_quantity,
                        s.refund_amount,
                        s.created_at
                    FROM mt_equity_package_sales s
                    JOIN mt_stores st ON s.org_code = st.org_code
                    WHERE 1=1
                """
                params = []

                if org_code:
                    query += " AND s.org_code = ?"
                    params.append(org_code)

                if start_date:
                    query += " AND s.date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND s.date <= ?"
                    params.append(end_date)

                query += " ORDER BY s.date DESC, st.store_name, s.package_name"

                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"Retrieved {len(results)} equity sales records")
                return results

        except sqlite3.Error as e:
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
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM mt_equity_package_sales
                    WHERE org_code = ?
                        AND date = ?
                        AND package_name = ?
                """, (org_code, date, package_name))

                row = cursor.fetchone()
                exists = row['count'] > 0

                if exists:
                    logger.debug(
                        f"Data exists for {org_code} / {package_name} on {date}"
                    )

                return exists

        except sqlite3.Error as e:
            logger.error(f"Error checking data existence: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the DatabaseManager class.
    """

    # Initialize database
    db = DatabaseManager()

    print("\n=== Database Initialized ===")
    print(f"Database location: {db.db_path}")

    # Example: Save some test data
    print("\n=== Saving Test Data ===")
    test_records = [
        {
            "org_code": "MD00007",
            "store_name": "宁桂杏山野烤肉（常熟世贸店）",
            "date": "2025-12-11",
            "package_name": "山海会员",
            "unit_price": 168.0,
            "quantity_sold": 5,
            "total_sales": 840.0,
            "refund_quantity": 0,
            "refund_amount": 0.0
        },
        {
            "org_code": "MD00007",
            "store_name": "宁桂杏山野烤肉（常熟世贸店）",
            "date": "2025-12-11",
            "package_name": "基础会员",
            "unit_price": 88.0,
            "quantity_sold": 3,
            "total_sales": 264.0,
            "refund_quantity": 1,
            "refund_amount": 88.0
        },
        {
            "org_code": "MD00006",
            "store_name": "宁桂杏山野烤肉（绵阳1958店）",
            "date": "2025-12-11",
            "package_name": "山海会员",
            "unit_price": 168.0,
            "quantity_sold": 2,
            "total_sales": 336.0,
            "refund_quantity": 0,
            "refund_amount": 0.0
        }
    ]

    saved = db.save_equity_package_sales(test_records)
    print(f"Saved {saved} records")

    # Display all stores
    print("\n=== All Stores ===")
    stores = db.get_stores()
    for store in stores:
        print(f"- {store['store_name']} ({store['org_code']})")

    # Query data
    print("\n=== Query All Sales ===")
    sales = db.get_equity_sales()
    print(f"Found {len(sales)} sales records")
    for record in sales:
        print(f"  {record['date']} | {record['org_code']} | {record['package_name']}: "
              f"{record['quantity_sold']} sold = ¥{record['total_sales']}")

    # Query by store
    print("\n=== Query Sales for MD00007 ===")
    sales = db.get_equity_sales(org_code="MD00007")
    for record in sales:
        print(f"  {record['date']} | {record['package_name']}: "
              f"{record['quantity_sold']} sold = ¥{record['total_sales']}")

    # Check if data exists
    print("\n=== Check Data Existence ===")
    exists = db.data_exists("MD00007", "2025-12-11", "山海会员")
    print(f"MD00007 / 山海会员 / 2025-12-11 exists: {exists}")

    exists = db.data_exists("MD00999", "2025-12-11", "山海会员")
    print(f"MD00999 / 山海会员 / 2025-12-11 exists: {exists}")
