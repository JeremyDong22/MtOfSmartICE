# 综合营业统计 Crawler - Extracts comprehensive business statistics
# v1.7 - Fixed: Increased wait time after clicking 查询 from 5s to 10s + 2s for data to load
#        Root cause: Large date ranges need more time to fetch and render data
# v1.6 - Fixed: Check if 按门店 is already selected before clicking to avoid unnecessary page refresh
#        Root cause: Clicking an already-selected radio button triggers page reload, clearing data
# v1.5 - Fixed: 2D grid algorithm for _flatten_headers() to properly handle mixed-depth headers
#        Root cause: Headers have 1-4 levels with different rowspan values (1,2,3,4)
#        - rowspan=4: Fixed columns (序号, 城市, 门店...) - 1 level
#        - rowspan=2: Most composition sub-headers (乳扇酒酿冰露...) - 3 levels
#        - rowspan=1: 微信/支付宝 need row 3 sub-headers (商家补贴...) - 4 levels
#        Previous code didn't track column occupancy, causing index mismatch in JSON keys
# v1.4 - Fixed: Explicitly select "按门店" view mode before querying
#        Root cause: page may default to "按集团" which has different column structure
# v1.3 - Added row validation to filter out group header rows with invalid data
# v1.2 - Select "按门店分组" view mode to get daily data with dates
#        Fixed pagination navigation for various UI styles
# v1.1 - Fixed date filter to work inside iframe (was using main page locators)
#
# Table Structure:
# - 20 fixed columns (序号, 城市, 门店, etc.)
# - Dynamic composition columns (渠道营业构成, 营业收入构成, etc.)
# - 4-level nested headers
#
# Data Storage:
# - Fixed columns: stored as individual fields in SQLite
# - Composition columns: stored as JSON in composition_data field

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class BusinessSummaryCrawler(BaseCrawler):
    """
    Crawler for 综合营业统计 (Comprehensive Business Statistics).

    This report provides detailed daily business metrics per store including:
    - Revenue, discounts, orders, customers
    - Channel breakdown (店内销售, 菜品销售)
    - Payment methods (现金, 扫码支付, 团购, etc.)
    - Discount breakdown (手动折扣, 优惠券, etc.)

    Note: Table is inside iframe `dpaas-report-container-*` with 4-level headers.
    """

    # Fixed column mappings (first 20 columns, excluding index which is col 0)
    FIXED_COLUMNS = [
        # (col_index, field_name, data_type)
        (1, 'city', 'text'),
        (2, 'store_name', 'text'),
        (3, 'business_date', 'date'),
        (4, 'store_created_at', 'datetime'),
        (5, 'operating_days', 'number'),
        (6, 'revenue', 'decimal'),
        (7, 'discount_amount', 'decimal'),
        (8, 'business_income', 'decimal'),
        (9, 'order_count', 'number'),
        (10, 'diner_count', 'number'),
        (11, 'table_count', 'number'),
        (12, 'per_capita_before_discount', 'decimal'),
        (13, 'per_capita_after_discount', 'decimal'),
        (14, 'avg_order_before_discount', 'decimal'),
        (15, 'avg_order_after_discount', 'decimal'),
        (16, 'table_opening_rate', 'percentage'),
        (17, 'table_turnover_rate', 'decimal'),
        (18, 'occupancy_rate', 'percentage'),
        (19, 'avg_dining_time', 'number'),
    ]

    def __init__(
        self,
        page,
        frame,
        db_manager,
        target_date: str,
        end_date: str = None,
        skip_navigation: bool = False,
        force_update: bool = False
    ):
        """
        Initialize the crawler.

        Args:
            page: Playwright page object
            frame: The main page frame (not the iframe - we'll find it ourselves)
            db_manager: Database manager instance
            target_date: Start date in YYYY-MM-DD format
            end_date: End date (defaults to target_date)
            skip_navigation: If True, skip filter configuration
        """
        super().__init__(page, frame, db_manager, target_date)
        self.end_date = end_date or target_date
        self.skip_navigation = skip_navigation
        self.force_update = force_update
        self.report_iframe = None  # Will store the dpaas-report iframe

    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        """
        Execute the crawl.

        Workflow:
        1. Find the report iframe (dpaas-report-container-*)
        2. Configure filters (date range)
        3. Click 查询
        4. Extract all pages of data
        5. Save to database

        Returns:
            Result dictionary with extracted data
        """
        logger.info(f"Starting 综合营业统计 crawl: {self.target_date} to {self.end_date}")

        try:
            # Step 1: Find the report iframe
            if not await self._find_report_iframe():
                return self.create_result(
                    False, store_id or "GROUP", store_name or "集团",
                    error="Could not find report iframe"
                )

            # Step 2: Configure filters
            if self.skip_navigation:
                logger.info("SKIP_NAVIGATION: Using current page state")
            else:
                if not await self._configure_filters():
                    return self.create_result(
                        False, store_id or "GROUP", store_name or "集团",
                        error="Filter configuration failed"
                    )

            # Step 3: Extract column headers (for flattening dynamic columns)
            column_names = await self._extract_column_headers()
            logger.info(f"Extracted {len(column_names)} column names")

            # Step 4: Extract all data with pagination
            all_data = await self._extract_all_pages(column_names)

            # Step 5: Get pagination info
            pagination_info = await self._get_pagination_info()

            # Step 6: Save to database
            save_stats = {"inserted": 0, "updated": 0, "skipped": 0}
            if all_data:
                save_stats = self.db.save_business_summary(all_data, force_update=self.force_update)
                logger.info(
                    f"Database: {save_stats['inserted']} inserted, "
                    f"{save_stats['updated']} updated, {save_stats['skipped']} skipped"
                )

            data = {
                "records": all_data,
                "record_count": len(all_data),
                "save_stats": save_stats,
                "date_range": {"start": self.target_date, "end": self.end_date},
                "pagination": pagination_info,
                "column_count": len(column_names)
            }

            logger.info(f"Extracted {len(all_data)} records")
            return self.create_result(True, store_id or "GROUP", store_name or "集团", data=data)

        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
            return self.create_result(
                False, store_id or "GROUP", store_name or "集团", error=str(e)
            )

    async def _find_report_iframe(self) -> bool:
        """
        Find the dpaas-report-container iframe that contains the data table.

        Returns:
            bool: True if iframe found
        """
        try:
            result = await self.page.evaluate('''() => {
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {
                    if (iframe.name && iframe.name.includes('dpaas-report')) {
                        return { found: true, name: iframe.name };
                    }
                }
                return { found: false };
            }''')

            if result.get('found'):
                iframe_name = result.get('name')
                logger.info(f"Found report iframe: {iframe_name}")

                # Get the frame object
                for frame in self.page.frames:
                    if iframe_name in (frame.name or ''):
                        self.report_iframe = frame
                        return True

            logger.error("Report iframe not found")
            return False

        except Exception as e:
            logger.error(f"Error finding report iframe: {e}")
            return False

    async def _configure_filters(self) -> bool:
        """
        Configure report filters (inside iframe):
        1. Expand filter section if collapsed
        2. Select "按门店" view mode (critical: page may default to "按集团" which has no store columns)
        3. Set date range
        4. Click 查询
        """
        try:
            logger.info("Configuring filters...")

            # First, expand the filter section if it's collapsed
            await self._expand_filter_section()
            await asyncio.sleep(0.5)

            # IMPORTANT: Explicitly select "按门店" view mode
            # The page may default to "按集团" which has a completely different table structure
            # (no 城市/门店 columns), causing extraction to fail
            await self._select_view_mode()
            await asyncio.sleep(0.5)

            # Set date range (filters are INSIDE the iframe)
            logger.info(f"Setting date range: {self.target_date} to {self.end_date}")
            await self._set_date_range(self.target_date, self.end_date)
            await asyncio.sleep(0.5)

            # Click query button (inside iframe)
            logger.info("Clicking 查询")
            query_clicked = await self.report_iframe.evaluate('''() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.includes('查询')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')

            if not query_clicked:
                logger.warning("Could not find 查询 button in iframe")
                return False

            # Wait for results to load - increased from 5s to 10s
            # The page needs time to fetch data and render the table
            logger.info("Waiting for query results to load...")
            await asyncio.sleep(10)

            # Re-find iframe (may have refreshed)
            if not await self._find_report_iframe():
                logger.warning("Could not re-find iframe after query")
                return False

            # Additional wait to ensure data is rendered in the iframe
            await asyncio.sleep(2)

            return True

        except Exception as e:
            logger.error(f"Filter configuration failed: {e}")
            return False

    async def _expand_filter_section(self) -> None:
        """Expand the filter section if it's collapsed (showing 展开筛选)."""
        try:
            # Check if filter is collapsed by looking for "展开筛选" text
            result = await self.report_iframe.evaluate('''() => {
                const allElements = document.body.innerText;
                if (allElements.includes('展开筛选')) {
                    // Filter is collapsed, need to expand
                    const links = document.querySelectorAll('a, span, div');
                    for (const el of links) {
                        if (el.textContent?.trim() === '展开筛选') {
                            el.click();
                            return { expanded: true };
                        }
                    }
                    return { expanded: false, reason: 'button_not_found' };
                }
                return { expanded: true, reason: 'already_expanded' };
            }''')

            if result.get('expanded'):
                logger.info(f"Filter section: {result.get('reason', 'expanded')}")
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"Could not expand filter: {result.get('reason')}")

        except Exception as e:
            logger.warning(f"Error expanding filter section: {e}")

    async def _select_view_mode(self) -> None:
        """
        Select "按门店" view mode under 统计维度 (Statistics Dimension).

        The view modes are:
        - 按门店: Shows per-store aggregated data (has 城市/门店 columns)
        - 按门店分组: Shows grouped by store with daily breakdown
        - 按组织机构: By organization structure
        - 按集团: Group-level aggregate (NO 城市/门店 columns - will break extraction)

        We need "按门店" to ensure the table has the expected column structure.
        """
        try:
            result = await self.report_iframe.evaluate('''() => {
                // First check if 按门店 is already selected
                const radios = document.querySelectorAll('input[type="radio"]');
                for (const radio of radios) {
                    const parent = radio.closest('label') || radio.parentElement;
                    const text = parent ? parent.textContent.trim() : '';
                    // Use exact match "按门店" to avoid matching "按门店分组"
                    if (text === '按门店') {
                        if (radio.checked) {
                            return { clicked: false, reason: 'already_selected' };
                        }
                        // Not selected, click it
                        radio.click();
                        return { clicked: true, method: 'radio' };
                    }
                }

                // Fallback: try clicking label/span
                const labels = document.querySelectorAll('label, span');
                for (const el of labels) {
                    const text = el.textContent?.trim() || '';
                    if (text === '按门店') {
                        el.click();
                        return { clicked: true, method: 'label' };
                    }
                }

                return { clicked: false, reason: 'radio_not_found' };
            }''')

            if result.get('clicked'):
                logger.info(f"Selected 按门店 view mode via {result.get('method')}")
                await asyncio.sleep(0.5)
            elif result.get('reason') == 'already_selected':
                logger.info("按门店 view mode already selected, skipping")
            else:
                logger.warning(f"Could not select view mode: {result.get('reason')}")

        except Exception as e:
            logger.warning(f"Error selecting view mode: {e}")

    async def _set_date_range(self, start_date: str, end_date: str) -> None:
        """
        Set date range using Playwright locators inside iframe.

        Uses triple-click to select all, then types the new date value.
        The date picker component requires YYYY/MM/DD format.
        """
        try:
            # Convert YYYY-MM-DD to YYYY/MM/DD format
            start_formatted = start_date.replace('-', '/')
            end_formatted = end_date.replace('-', '/')

            # Get locators for date inputs inside iframe
            start_input = self.report_iframe.locator('input[placeholder="开始日期"]')
            end_input = self.report_iframe.locator('input[placeholder="结束日期"]')

            # Wait for date inputs to be visible (iframe content may still be loading)
            logger.info("Waiting for date inputs to become visible...")
            try:
                await start_input.wait_for(state='visible', timeout=10000)
            except Exception:
                logger.warning("Date input not found in iframe, trying main page...")
                # Fallback to main page if not in iframe
                start_input = self.page.locator('input[placeholder="开始日期"]')
                end_input = self.page.locator('input[placeholder="结束日期"]')
                await start_input.wait_for(state='visible', timeout=10000)

            # Set start date: triple-click to select all, then type
            logger.info(f"Setting start date to: {start_formatted}")
            await start_input.click(click_count=3)  # Triple-click to select all
            await asyncio.sleep(0.2)
            await start_input.fill(start_formatted)
            await asyncio.sleep(0.3)
            await start_input.press('Enter')
            await asyncio.sleep(0.5)

            # Press Escape to close picker
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.3)

            # Set end date: triple-click to select all, then type
            logger.info(f"Setting end date to: {end_formatted}")
            await end_input.click(click_count=3)  # Triple-click to select all
            await asyncio.sleep(0.2)
            await end_input.fill(end_formatted)
            await asyncio.sleep(0.3)
            await end_input.press('Enter')
            await asyncio.sleep(0.5)

            # Press Escape to close picker
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.3)

            # Verify the values were set
            start_value = await start_input.input_value()
            end_value = await end_input.input_value()
            logger.info(f"Date range after setting: {start_value} to {end_value}")

        except Exception as e:
            logger.error(f"Error setting date range: {e}")

    async def _extract_column_headers(self) -> List[str]:
        """
        Extract and flatten the 4-level table headers.

        Returns:
            List of flattened column names like "渠道营业构成-店内销售-营业额(元)"
        """
        try:
            headers = await self.report_iframe.evaluate('''() => {
                const ths = document.querySelectorAll('th');
                const result = [];

                for (const th of ths) {
                    result.push({
                        text: th.textContent?.trim(),
                        colspan: th.getAttribute('colspan') || '1',
                        rowspan: th.getAttribute('rowspan') || '1',
                        rowIndex: th.closest('tr')?.rowIndex
                    });
                }

                return result;
            }''')

            # Build flattened column names
            return self._flatten_headers(headers)

        except Exception as e:
            logger.error(f"Error extracting column headers: {e}")
            return []

    def _flatten_headers(self, headers: List[Dict]) -> List[str]:
        """
        Flatten the 4-level nested headers into single column names using 2D grid.

        v1.5 - Fixed bug: Now properly tracks column occupancy with rowspan/colspan.
        Uses 2D grid algorithm to handle mixed-depth headers (1-4 levels).

        Strategy:
        1. Calculate total columns from row 0
        2. Create 4 x N grid (4 rows, N columns)
        3. Fill grid respecting rowspan/colspan (mark occupied cells)
        4. Read down each column to build hierarchical path
        """
        # Group headers by row (0-3)
        rows = {0: [], 1: [], 2: [], 3: []}
        for h in headers:
            row_idx = h.get('rowIndex')
            if row_idx is not None and row_idx in rows:
                rows[row_idx].append(h)

        # Calculate total columns from row 0 (sum of colspans)
        total_cols = sum(int(h['colspan']) for h in rows[0])
        logger.info(f"Header grid: 4 rows x {total_cols} columns")

        # Create 2D grid: grid[row][col] = header_text or None
        grid = [[None for _ in range(total_cols)] for _ in range(4)]

        # Track which cells are occupied (by rowspan from previous rows)
        occupied = [[False for _ in range(total_cols)] for _ in range(4)]

        # Fill grid row by row
        for row_idx in range(4):
            col_cursor = 0  # Current column position in this row

            for h in rows[row_idx]:
                text = h['text']
                colspan = int(h['colspan'])
                rowspan = int(h['rowspan'])

                # Skip columns already occupied by previous rowspans
                while col_cursor < total_cols and occupied[row_idx][col_cursor]:
                    col_cursor += 1

                if col_cursor >= total_cols:
                    break

                # Fill this header into grid, respecting colspan and rowspan
                for dr in range(rowspan):
                    if row_idx + dr >= 4:
                        break
                    for dc in range(colspan):
                        if col_cursor + dc >= total_cols:
                            break
                        grid[row_idx + dr][col_cursor + dc] = text
                        occupied[row_idx + dr][col_cursor + dc] = True

                col_cursor += colspan

        # Build column names by reading down each column
        column_names = []
        for col in range(total_cols):
            parts = []
            for row in range(4):
                cell = grid[row][col]
                # Add to path if non-empty and not duplicate of previous
                if cell and (not parts or parts[-1] != cell):
                    parts.append(cell)

            column_names.append('-'.join(parts) if parts else f"Col{col}")

        logger.info(f"Flattened {len(column_names)} column headers")
        return column_names

    async def _get_pagination_info(self) -> Dict[str, Any]:
        """Get pagination information from the iframe."""
        try:
            info = await self.report_iframe.evaluate('''() => {
                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条记录/);
                const totalRecords = totalMatch ? parseInt(totalMatch[1]) : 0;

                // Find active page
                const pageItems = document.querySelectorAll('li[class*="ant-pagination-item"]');
                let currentPage = 1;
                for (const item of pageItems) {
                    if (item.classList.contains('ant-pagination-item-active')) {
                        currentPage = parseInt(item.textContent?.trim() || '1');
                        break;
                    }
                }

                const perPage = 20;
                const totalPages = Math.ceil(totalRecords / perPage);

                return {
                    total_records: totalRecords,
                    total_pages: totalPages,
                    current_page: currentPage,
                    per_page: perPage
                };
            }''')
            logger.info(f"Pagination: {info['total_records']} records, {info['total_pages']} pages")
            return info
        except Exception as e:
            logger.warning(f"Error getting pagination: {e}")
            return {"total_records": 0, "total_pages": 1, "current_page": 1, "per_page": 20}

    async def _extract_table_data(self, column_names: List[str]) -> List[Dict[str, Any]]:
        """
        Extract data from current page's table.

        Args:
            column_names: List of flattened column names

        Returns:
            List of record dictionaries
        """
        try:
            raw_data = await self.report_iframe.evaluate('''() => {
                const rows = [];
                const tbody = document.querySelector('tbody');
                if (!tbody) return rows;

                const trs = tbody.querySelectorAll('tr');
                for (const tr of trs) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length < 10) continue;  // Skip header or empty rows

                    const rowData = [];
                    for (const cell of cells) {
                        rowData.push(cell.textContent?.trim() || '');
                    }

                    // Skip summary row (contains "合计")
                    if (rowData[0] === '合计' || rowData[1] === '合计') continue;

                    rows.push(rowData);
                }

                return rows;
            }''')

            # Debug: log first row's structure
            if raw_data and len(raw_data) > 0:
                first_row = raw_data[0]
                logger.info(f"First row structure ({len(first_row)} cols): {first_row[:10]}...")

            # Parse into structured records
            parsed_data = []
            for row in raw_data:
                try:
                    record = self._parse_row(row, column_names)
                    if record:
                        parsed_data.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")

            logger.info(f"Extracted {len(parsed_data)} records from current page")
            return parsed_data

        except Exception as e:
            logger.error(f"Error extracting table data: {e}")
            return []

    def _parse_row(self, row: List[str], column_names: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a row of data into a structured record.

        Args:
            row: List of cell values
            column_names: List of column names

        Returns:
            Parsed record dictionary or None
        """
        if len(row) < 20:
            return None

        record = {}

        # Parse fixed columns (skip index at position 0)
        for col_idx, field_name, data_type in self.FIXED_COLUMNS:
            if col_idx >= len(row):
                continue

            value = row[col_idx]

            if data_type == 'number':
                record[field_name] = int(self.parse_number(value))
            elif data_type == 'decimal':
                record[field_name] = self.parse_number(value)
            elif data_type == 'percentage':
                # Keep as string with % or parse to decimal
                record[field_name] = value
            elif data_type == 'date':
                # Convert YYYY/MM/DD to YYYY-MM-DD
                record[field_name] = value.replace('/', '-')
            else:
                record[field_name] = value

        # Validate record: skip group header rows or malformed data
        # Valid business_date should be in YYYY-MM-DD or YYYY/MM/DD format
        business_date = record.get('business_date', '')
        if not self._is_valid_date(business_date):
            logger.debug(f"Skipping row with invalid business_date: {business_date}")
            return None

        # Valid store_name should not be a number (which would indicate shifted columns)
        store_name = record.get('store_name', '')
        if not store_name or store_name.isdigit():
            logger.debug(f"Skipping row with invalid store_name: {store_name}")
            return None

        # Parse composition columns (starting from column 20)
        composition_data = {}
        for i in range(20, min(len(row), len(column_names))):
            col_name = column_names[i] if i < len(column_names) else f"col_{i}"
            value = row[i] if i < len(row) else ''

            # Try to parse as number
            try:
                num_val = self.parse_number(value)
                composition_data[col_name] = num_val
            except:
                composition_data[col_name] = value

        record['composition_data'] = json.dumps(composition_data, ensure_ascii=False)

        return record

    def _is_valid_date(self, date_str: str) -> bool:
        """
        Check if a string looks like a valid date (YYYY-MM-DD or YYYY/MM/DD format).

        Args:
            date_str: String to validate

        Returns:
            bool: True if valid date format
        """
        if not date_str:
            return False

        # Normalize separators
        normalized = date_str.replace('/', '-')

        # Check format: should be YYYY-MM-DD
        parts = normalized.split('-')
        if len(parts) != 3:
            return False

        try:
            year, month, day = parts
            # Year should be 4 digits starting with 20
            if len(year) != 4 or not year.startswith('20'):
                return False
            # Month should be 1-12
            if not (1 <= int(month) <= 12):
                return False
            # Day should be 1-31
            if not (1 <= int(day) <= 31):
                return False
            return True
        except (ValueError, TypeError):
            return False

    async def _go_to_page(self, target_page: int) -> bool:
        """
        Navigate to specific page number by clicking page number or next button.

        Args:
            target_page: Page number to navigate to

        Returns:
            bool: True if navigation successful
        """
        try:
            result = await self.report_iframe.evaluate('''(targetPage) => {
                // Method 1: Try clicking page number directly (various pagination styles)
                // Check li items with page numbers
                const listItems = document.querySelectorAll('li');
                for (const item of listItems) {
                    const text = item.textContent?.trim();
                    // Match exact page number (avoid matching within longer text)
                    if (text === String(targetPage)) {
                        item.click();
                        return { success: true, method: 'listitem_click' };
                    }
                }

                // Method 2: Check ant-pagination-item class elements
                const pageItems = document.querySelectorAll('[class*="pagination-item"]');
                for (const item of pageItems) {
                    if (item.textContent?.trim() === String(targetPage)) {
                        item.click();
                        return { success: true, method: 'pagination_item_click' };
                    }
                }

                // Method 3: Use the "跳至" input field if available
                const jumpInputs = document.querySelectorAll('input');
                for (const input of jumpInputs) {
                    // Find the jump-to input (usually near "跳至" text)
                    const parent = input.parentElement;
                    if (parent && parent.textContent?.includes('跳至')) {
                        input.value = String(targetPage);
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                        return { success: true, method: 'jump_input' };
                    }
                }

                return { success: false, reason: 'page_not_found', available: Array.from(listItems).map(li => li.textContent?.trim()).slice(0, 10) };
            }''', target_page)

            if result.get('success'):
                logger.info(f"Navigated to page {target_page} via {result.get('method')}")
                await asyncio.sleep(2)  # Wait for data to load
                return True

            logger.warning(f"Could not navigate to page {target_page}: {result.get('reason')}")
            if result.get('available'):
                logger.debug(f"Available items: {result.get('available')}")
            return False

        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}")
            return False

    async def _extract_all_pages(self, column_names: List[str]) -> List[Dict[str, Any]]:
        """
        Extract data from all pages.

        Args:
            column_names: List of flattened column names

        Returns:
            List of all extracted records
        """
        all_data = []

        pagination = await self._get_pagination_info()
        total_pages = pagination.get('total_pages', 1)

        # Always start from page 1
        current_page = pagination.get('current_page', 1)
        if current_page != 1:
            await self._go_to_page(1)
            await asyncio.sleep(1)

        logger.info(f"Extracting data from {total_pages} pages...")

        for page_num in range(1, total_pages + 1):
            logger.info(f"Extracting page {page_num}/{total_pages}")
            page_data = await self._extract_table_data(column_names)
            all_data.extend(page_data)

            if page_num < total_pages:
                await self._go_to_page(page_num + 1)
                await asyncio.sleep(1)

        logger.info(f"Total records extracted: {len(all_data)}")
        return all_data
