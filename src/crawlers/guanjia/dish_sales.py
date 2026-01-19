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

            # Click query button
            logger.info("Clicking 查询")
            query_clicked = await self.page.evaluate('''() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent || '';
                    if (text.includes('查询') && !text.includes('常用')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')

            if not query_clicked:
                logger.warning("Could not find 查询 button")
                return False

            # Wait for results to load (dish sales needs more time)
            await asyncio.sleep(10)

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
            # Click the sales method dropdown (third .ant-select on the page)
            result = await self.page.evaluate('''() => {
                const selects = document.querySelectorAll('.ant-select');
                // Find the one with '单品+套餐' text
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

            # Select "单品+套餐明细" option
            result2 = await self.page.evaluate('''() => {
                // Find the dropdown menu items
                const items = document.querySelectorAll('.ant-select-dropdown-menu-item');
                for (const item of items) {
                    const text = item.textContent?.trim() || '';
                    if (text === '单品+套餐明细') {
                        item.click();
                        return { success: true, selected: text };
                    }
                }

                // If not found, list all available options for debugging
                const allOptions = [];
                for (const item of items) {
                    allOptions.push(item.textContent?.trim());
                }
                return { success: false, reason: 'option_not_found', available: allOptions };
            }''')

            if result2.get('success'):
                logger.info(f"Selected 销售方式: {result2.get('selected')}")
            else:
                logger.warning(f"Could not select option: {result2.get('reason')}, available: {result2.get('available')}")

        except Exception as e:
            logger.warning(f"Error setting sales method: {e}")

    async def _set_date_range(self, start_date: str, end_date: str) -> None:
        """Set date range using JavaScript (inputs are readonly)."""
        try:
            # Convert YYYY-MM-DD to YYYY/MM/DD
            start_formatted = start_date.replace('-', '/')
            end_formatted = end_date.replace('-', '/')

            # Set dates using JavaScript (inputs are readonly)
            # Note: inputs[0] is week selector, inputs[1] and inputs[2] are the date range
            await self.page.evaluate('''(dates) => {
                const inputs = document.querySelectorAll('input[placeholder="请选择日期"]');
                if (inputs.length >= 3) {
                    inputs[1].value = dates.start;
                    inputs[2].value = dates.end;

                    // Trigger change events
                    inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
                    inputs[1].dispatchEvent(new Event('change', { bubbles: true }));
                    inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
                    inputs[2].dispatchEvent(new Event('change', { bubbles: true }));
                }
            }''', {'start': start_formatted, 'end': end_formatted})

            await asyncio.sleep(0.5)
            logger.info(f"Set date range: {start_formatted} to {end_formatted}")

        except Exception as e:
            logger.error(f"Error setting date range: {e}")

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
                    per_page: perPage
                };
            }''')
            logger.info(f"Pagination: {info['total_records']} records, {info['total_pages']} pages")
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
