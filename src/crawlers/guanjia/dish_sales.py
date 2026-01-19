# 菜品综合统计 Crawler - Extracts dish-level sales data
# v1.0 - Initial implementation
#
# This crawler extracts comprehensive dish sales statistics including:
# - Sales quantity and amount per dish
# - Returns, gifts, and order statistics
# - Data grouped by store (using "按门店统计" checkbox)
#
# Key differences from other crawlers:
# - Data is on main page (not in iframe)
# - Uses "按门店统计" checkbox to get all stores at once
# - More complex table structure with 30+ columns

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class DishSalesCrawler(BaseCrawler):
    """
    Crawler for 菜品综合统计 (Dish Comprehensive Statistics).

    Expects to be called AFTER site navigation is complete.
    Data is on the main page (not in iframe).

    Data extracted per row:
    - 门店 (store_name): Store name
    - 机构编码 (org_code): Store code (e.g., MD00012)
    - 菜品名称 (dish_name): Dish name
    - 30+ metrics including sales, returns, gifts, orders
    """

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
            frame: Not used (data is on main page)
            db_manager: Database manager instance
            target_date: Start date in YYYY-MM-DD format
            end_date: End date (if None or same as target_date, will be set to target_date + 1 day)
            skip_navigation: If True, skip filter configuration
            force_update: If True, force update existing records
        """
        super().__init__(page, frame, db_manager, target_date)

        # Dish sales requires SAME date for start and end (not a range)
        # If dates are different, data will aggregate across dates
        if not end_date:
            self.end_date = target_date
        else:
            self.end_date = end_date

        if self.end_date != target_date:
            logger.warning(f"Dish sales works best with same start/end date, but got {target_date} to {self.end_date}")

        self.skip_navigation = skip_navigation
        self.force_update = force_update

    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        """
        Execute the crawl.

        Workflow:
        1. Configure filters (checkboxes, date range)
        2. Click 查询
        3. Extract all pages of data
        4. Save to database

        Returns:
            Result dictionary with extracted data
        """
        logger.info(f"Starting 菜品综合统计 crawl: {self.target_date} to {self.end_date}")

        try:
            # Step 1: Configure filters
            if self.skip_navigation:
                logger.info("SKIP_NAVIGATION: Using current page state")
            else:
                if not await self._configure_filters():
                    return self.create_result(
                        False, store_id or "GROUP", store_name or "集团",
                        error="Filter configuration failed"
                    )

            # Step 2: Extract all data with pagination
            all_data = await self._extract_all_pages()

            # Step 3: Get pagination info
            pagination_info = await self._get_pagination_info()

            # Step 4: Save to database
            save_stats = {"inserted": 0, "updated": 0, "skipped": 0}
            if all_data:
                save_stats = self.db.save_dish_sales(all_data, force_update=self.force_update)
                logger.info(
                    f"Database: {save_stats['inserted']} inserted, "
                    f"{save_stats['updated']} updated, {save_stats['skipped']} skipped"
                )

            data = {
                "records": all_data,
                "record_count": len(all_data),
                "save_stats": save_stats,
                "date_range": {"start": self.target_date, "end": self.end_date},
                "pagination": pagination_info
            }

            logger.info(f"Extracted {len(all_data)} records")
            return self.create_result(True, store_id or "GROUP", store_name or "集团", data=data)

        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
            return self.create_result(
                False, store_id or "GROUP", store_name or "集团", error=str(e)
            )

    async def _configure_filters(self) -> bool:
        """
        Configure report filters:
        1. Ensure "按门店统计" checkbox is checked
        2. Ensure "同名菜品合并统计" checkbox is checked
        3. Set 销售方式 to "单品+套餐明细"
        4. Set date range
        5. Click 查询
        """
        try:
            logger.info("Configuring filters...")

            # Wait for page to fully load
            await asyncio.sleep(2)

            # Ensure checkboxes are checked
            await self._ensure_checkboxes_checked()
            await asyncio.sleep(0.5)

            # Set 销售方式 to "单品+套餐明细"
            logger.info("Setting 销售方式 to 单品+套餐明细")
            await self._set_sales_method()
            await asyncio.sleep(0.5)

            # Set date range
            logger.info(f"Setting date range: {self.target_date} to {self.end_date}")
            await self._set_date_range(self.target_date, self.end_date)
            await asyncio.sleep(0.5)

            # CRITICAL: Verify dates are set correctly before querying
            # If date range spans multiple days, data will be aggregated and incorrect
            await self._verify_dates_set_correctly()

            # Click query button using specific selector
            logger.info("Clicking 查询")
            query_clicked = await self.page.evaluate('''() => {
                const selector = '#__root_wrapper_rms-report > div > div > div > div.auto2-page-slot_filter > div > div > div.auto2-query-item.action > button.ant-btn.ant-btn-primary';
                const btn = document.querySelector(selector);
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }''')

            if not query_clicked:
                logger.warning("Could not find 查询 button")
                return False

            # Wait for results to load - dish sales can take 15-20 seconds
            logger.info("Waiting for query results to load...")

            # Wait for loading indicators to disappear with retry logic
            max_wait = 45  # Maximum 45 seconds (increased for slow network)
            wait_interval = 2
            elapsed = 0
            retry_count = 0
            max_retries = 2

            while elapsed < max_wait:
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval

                # Check if data has loaded by looking for pagination text
                has_data = await self.page.evaluate('''() => {
                    return document.body.innerText.includes('条记录');
                }''')

                if has_data:
                    logger.info(f"Query results loaded after {elapsed} seconds")
                    break

                # Check for error messages
                has_error = await self.page.evaluate('''() => {
                    const text = document.body.innerText;
                    return text.includes('查询失败') || text.includes('网络错误') || text.includes('加载失败');
                }''')

                if has_error and retry_count < max_retries:
                    logger.warning(f"Query failed, retrying ({retry_count + 1}/{max_retries})...")
                    # Click query button again
                    await self.page.evaluate('''() => {
                        const selector = '#__root_wrapper_rms-report > div > div > div > div.auto2-page-slot_filter > div > div > div.auto2-query-item.action > button.ant-btn.ant-btn-primary';
                        const btn = document.querySelector(selector);
                        if (btn) btn.click();
                    }''')
                    retry_count += 1
                    elapsed = 0  # Reset timer for retry
                    continue

                logger.debug(f"Still waiting for results... ({elapsed}s)")

            if elapsed >= max_wait:
                logger.error(f"Query results did not load after {max_wait} seconds")
                return False

            return True

        except Exception as e:
            logger.error(f"Filter configuration failed: {e}")
            return False

    async def _ensure_checkboxes_checked(self) -> None:
        """Ensure both required checkboxes are checked."""
        try:
            result = await self.page.evaluate('''() => {
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                let byStoreChecked = false;
                let mergeNameChecked = false;

                for (const cb of checkboxes) {
                    const grandparent = cb.parentElement?.parentElement;
                    const label = grandparent?.textContent || '';
                    if (label.includes('按门店统计')) {
                        if (!cb.checked) cb.click();
                        byStoreChecked = true;
                    } else if (label.includes('同名菜品合并统计')) {
                        if (!cb.checked) cb.click();
                        mergeNameChecked = true;
                    }
                }

                return { byStoreChecked, mergeNameChecked };
            }''')

            logger.info(f"Checkboxes: {result}")

        except Exception as e:
            logger.warning(f"Error checking checkboxes: {e}")

    async def _set_sales_method(self) -> None:
        """Set 销售方式 to '单品+套餐明细' by clicking dropdown and selecting option."""
        try:
            # Click the sales method dropdown
            result = await self.page.evaluate('''() => {
                const selects = document.querySelectorAll('.ant-select');
                for (const select of selects) {
                    const text = select.textContent || '';
                    if (text.includes('单品+套餐') && !text.includes('明细')) {
                        select.click();
                        return { success: true, step: 'opened_dropdown' };
                    }
                }
                return { success: false, reason: 'dropdown_not_found' };
            }''')

            if not result.get('success'):
                logger.warning(f"Could not open 销售方式 dropdown: {result.get('reason')}")
                return

            # Wait for dropdown to open
            await asyncio.sleep(1.5)

            # Select "单品+套餐明细" using the specific CSS selector
            result2 = await self.page.evaluate('''() => {
                const selector = '#rc-tree-select-list_3 > ul > li:nth-child(4) > span.ant-select-tree-node-content-wrapper.ant-select-tree-node-content-wrapper-normal > span';
                const element = document.querySelector(selector);
                if (element) {
                    element.click();
                    return { success: true, selected: '单品+套餐明细' };
                }
                return { success: false, reason: 'selector_not_found' };
            }''')

            if result2.get('success'):
                logger.info(f"Selected 销售方式: {result2.get('selected')}")
            else:
                logger.warning(f"Could not select option: {result2.get('reason')}")

        except Exception as e:
            logger.warning(f"Error setting sales method: {e}")

    async def _set_date_range(self, start_date: str, end_date: str) -> None:
        """Set date range by clicking calendar cells."""
        try:
            from datetime import datetime

            # Parse dates
            start_formatted = start_date.replace('-', '/')
            end_formatted = end_date.replace('-', '/')

            logger.info(f"=== DATE SETTING START ===")
            logger.info(f"Target: {start_formatted} to {end_formatted}")

            # Check if dates are already set correctly
            current_values = await self.page.evaluate('''() => {
                const inputs = document.querySelectorAll('input[placeholder="请选择日期"]');
                if (inputs.length < 2) return {found: inputs.length};
                const startIdx = inputs.length === 2 ? 0 : 1;
                const endIdx = inputs.length === 2 ? 1 : 2;
                return {
                    found: inputs.length,
                    start: inputs[startIdx]?.value || '',
                    end: inputs[endIdx]?.value || ''
                };
            }''')

            logger.info(f"Current dates: {current_values.get('start')} to {current_values.get('end')}")

            if (current_values.get('start') == start_formatted and
                current_values.get('end') == end_formatted):
                logger.info(f"✓ Dates already correct, skipping date selection")
                logger.info(f"=== DATE SETTING COMPLETE ===")
                return

            # Parse dates to Chinese format for calendar cell titles
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_title = f"{start_dt.year}年{start_dt.month}月{start_dt.day}日"
            end_title = f"{end_dt.year}年{end_dt.month}月{end_dt.day}日"

            logger.info(f"Looking for calendar cells: {start_title}, {end_title}")

            # Click first input to open calendar
            await self.page.evaluate('''() => {
                const inputs = document.querySelectorAll('input[placeholder="请选择日期"]');
                const startIdx = inputs.length === 2 ? 0 : 1;
                inputs[startIdx]?.click();
            }''')
            await asyncio.sleep(1)

            # Click start date
            result1 = await self.page.evaluate(f'''() => {{
                const cell = document.querySelector('.ant-calendar-cell[title="{start_title}"]');
                if (cell) {{
                    cell.click();
                    return {{success: true}};
                }}
                return {{success: false, error: 'Start date cell not found'}};
            }}''')

            if not result1.get('success'):
                raise Exception(f"Failed to click start date: {result1.get('error')}")

            logger.info(f"✓ Clicked start date: {start_title}")
            await asyncio.sleep(0.5)

            # Click end date
            result2 = await self.page.evaluate(f'''() => {{
                const cell = document.querySelector('.ant-calendar-cell[title="{end_title}"]');
                if (cell) {{
                    cell.click();
                    return {{success: true}};
                }}
                return {{success: false, error: 'End date cell not found'}};
            }}''')

            if not result2.get('success'):
                raise Exception(f"Failed to click end date: {result2.get('error')}")

            logger.info(f"✓ Clicked end date: {end_title}")
            await asyncio.sleep(0.5)
            logger.info(f"=== DATE SETTING COMPLETE ===")

        except Exception as e:
            logger.error(f"Date setting failed: {e}")
            raise

    async def _verify_dates_set_correctly(self) -> None:
        """
        Verify that dates shown in browser match target dates.
        CRITICAL: If dates don't match, data will be aggregated across multiple days and incorrect.
        """
        try:
            start_formatted = self.target_date.replace('-', '/')
            end_formatted = self.end_date.replace('-', '/')

            # Get actual dates shown in browser
            actual_dates = await self.page.evaluate('''() => {
                const inputs = document.querySelectorAll('input[placeholder="请选择日期"]');
                if (inputs.length < 2) return {found: inputs.length};
                const startIdx = inputs.length === 2 ? 0 : 1;
                const endIdx = inputs.length === 2 ? 1 : 2;
                return {
                    found: inputs.length,
                    start: inputs[startIdx]?.value || '',
                    end: inputs[endIdx]?.value || ''
                };
            }''')

            actual_start = actual_dates.get('start')
            actual_end = actual_dates.get('end')

            logger.info(f"Date verification: Expected {start_formatted} to {end_formatted}, Got {actual_start} to {actual_end}")

            if actual_start != start_formatted or actual_end != end_formatted:
                error_msg = (
                    f"DATE MISMATCH ERROR: Dates in browser don't match target dates!\n"
                    f"Expected: {start_formatted} to {end_formatted}\n"
                    f"Actual:   {actual_start} to {actual_end}\n"
                    f"This will cause data aggregation across multiple days and produce incorrect results.\n"
                    f"Stopping crawl to prevent data corruption."
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info("✓ Date verification passed")

        except Exception as e:
            logger.error(f"Date verification failed: {e}")
            raise

    async def _get_pagination_info(self) -> Dict[str, Any]:
        """Get pagination information."""
        try:
            info = await self.page.evaluate('''() => {
                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条记录/);
                const totalRecords = totalMatch ? parseInt(totalMatch[1]) : 0;

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
                    per_page: perPage,
                    debug_match: totalMatch ? totalMatch[0] : null,
                    debug_has_text: allText.includes('条记录')
                };
            }''')
            logger.info(f"Pagination: {info['total_records']} records, {info['total_pages']} pages (debug: match={info.get('debug_match')}, has_text={info.get('debug_has_text')})")
            return info
        except Exception as e:
            logger.warning(f"Error getting pagination: {e}")
            return {"total_records": 0, "total_pages": 1, "current_page": 1, "per_page": 20}

    async def _extract_table_data(self) -> List[Dict[str, Any]]:
        """Extract data from current page's table."""
        try:
            raw_data = await self.page.evaluate('''() => {
                const rows = [];

                // Find the correct table by looking for headers with "门店" and "机构编码"
                const tables = document.querySelectorAll('table');
                let targetTbody = null;

                for (const table of tables) {
                    const thead = table.querySelector('thead');
                    if (!thead) continue;

                    const headerText = thead.textContent || '';
                    if (headerText.includes('门店') && headerText.includes('机构编码')) {
                        targetTbody = table.querySelector('tbody');
                        break;
                    }
                }

                if (!targetTbody) return rows;

                const trs = targetTbody.querySelectorAll('tr');
                for (const tr of trs) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length < 10) continue;

                    // Skip rows with virtual scrolling (height: 0px)
                    const firstCell = cells[0];
                    const firstDiv = firstCell?.querySelector('div');
                    if (firstDiv) {
                        const style = firstDiv.getAttribute('style') || '';
                        if (style.includes('height: 0px') || style.includes('height:0px')) {
                            continue;
                        }
                    }

                    const rowData = [];
                    for (const cell of cells) {
                        rowData.push(cell.textContent?.trim() || '');
                    }

                    // Skip summary row
                    if (rowData[0] === '合计' || rowData[1] === '合计') continue;

                    rows.push(rowData);
                }

                return rows;
            }''')

            # Parse into structured records
            parsed_data = []
            for row in raw_data:
                try:
                    record = self._parse_row(row)
                    if record:
                        parsed_data.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")

            logger.info(f"Extracted {len(parsed_data)} records from current page")
            return parsed_data

        except Exception as e:
            logger.error(f"Error extracting table data: {e}")
            return []

    def _parse_row(self, row: List[str]) -> Optional[Dict[str, Any]]:
        """Parse a row of data into a structured record."""
        if len(row) < 30:
            return None

        try:
            # Extract business_date from the date range
            # Since we're querying a date range, we need to use the target_date
            business_date = self.target_date

            record = {
                "store_name": row[1],  # 门店
                "org_code": row[2],    # 机构编码
                "business_date": business_date,
                "dish_name": row[3],   # 菜品名称
                "sales_quantity": int(self.parse_number(row[4])) if row[4] else None,
                "sales_quantity_pct": self.parse_number(row[5]),
                "price_before_discount": self.parse_number(row[6]),
                "price_after_discount": self.parse_number(row[7]),
                "sales_amount": self.parse_number(row[8]),
                "sales_amount_pct": self.parse_number(row[9]),
                "discount_amount": self.parse_number(row[10]),
                "dish_discount_pct": self.parse_number(row[11]),
                "dish_income": self.parse_number(row[12]),
                "dish_income_pct": self.parse_number(row[13]),
                "order_quantity": int(self.parse_number(row[14])) if row[14] else None,
                "order_amount": self.parse_number(row[15]),
                "return_quantity": int(self.parse_number(row[16])) if row[16] else None,
                "return_amount": self.parse_number(row[17]),
                "return_quantity_pct": self.parse_number(row[18]),
                "return_amount_pct": self.parse_number(row[19]),
                "return_rate": self.parse_number(row[20]),
                "return_order_count": int(self.parse_number(row[21])) if row[21] else None,
                "gift_quantity": int(self.parse_number(row[22])) if row[22] else None,
                "gift_amount": self.parse_number(row[23]),
                "gift_quantity_pct": self.parse_number(row[24]),
                "gift_amount_pct": self.parse_number(row[25]),
                "dish_order_count": int(self.parse_number(row[26])) if row[26] else None,
                "related_order_amount": self.parse_number(row[27]),
                "sales_per_thousand": self.parse_number(row[28]),
                "order_rate": self.parse_number(row[29]),
                "customer_click_rate": self.parse_number(row[30]) if len(row) > 30 else None,
            }

            return record

        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
            return None

    async def _go_to_page(self, target_page: int) -> bool:
        """Navigate to specific page number."""
        try:
            result = await self.page.evaluate('''(targetPage) => {
                const listItems = document.querySelectorAll('li');
                for (const item of listItems) {
                    const text = item.textContent?.trim();
                    if (text === String(targetPage)) {
                        item.click();
                        return { success: true };
                    }
                }
                return { success: false };
            }''', target_page)

            if result.get('success'):
                logger.info(f"Navigated to page {target_page}")
                await asyncio.sleep(2)
                return True

            logger.warning(f"Could not navigate to page {target_page}")
            return False

        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}")
            return False

    async def _extract_all_pages(self) -> List[Dict[str, Any]]:
        """Extract data from all pages."""
        all_data = []

        # Wait a bit more for pagination to render
        await asyncio.sleep(2)

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
            page_data = await self._extract_table_data()
            all_data.extend(page_data)

            if page_num < total_pages:
                await self._go_to_page(page_num + 1)
                await asyncio.sleep(1)

        logger.info(f"Total records extracted: {len(all_data)}")
        return all_data
