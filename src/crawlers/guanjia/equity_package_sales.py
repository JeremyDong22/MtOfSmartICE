# 权益包售卖汇总表 Crawler - Extracts equity package sales data
# v3.0 - Refactored: Navigation logic moved to sites/meituan_guanjia.py
#
# This crawler focuses ONLY on:
# - Filter configuration (checkboxes, date range)
# - Data extraction from table
# - Pagination handling
#
# Navigation is handled by MeituanGuanjiaSite

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class EquityPackageSalesCrawler(BaseCrawler):
    """
    Crawler for 权益包售卖汇总表 (Equity Package Sales Summary).

    Expects to be called AFTER site navigation is complete.
    The frame should already be set to the correct iframe.

    Data extracted per row:
    - 机构编码 (org_code): Store code (e.g., MD00007)
    - 售卖门店 (store_name): Store name
    - 日期 (date): Business date
    - 权益包名称 (package_name): Package name
    - 售卖单价 (unit_price): Unit price
    - 售卖数量 (quantity_sold): Quantity sold
    - 售卖总价 (total_sales): Total sales amount
    - 退款数量 (refund_quantity): Refund quantity
    - 退款总价 (refund_amount): Refund amount
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
            frame: The iframe containing the report (from site.get_frame())
            db_manager: Database manager instance
            target_date: Start date in YYYY-MM-DD format
            end_date: End date (defaults to target_date)
            skip_navigation: If True, skip filter configuration
            force_update: If True, force update existing records
        """
        super().__init__(page, frame, db_manager, target_date)
        self.end_date = end_date or target_date
        self.skip_navigation = skip_navigation
        self.force_update = force_update

    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        """
        Execute the crawl.

        Workflow (navigation already done by site):
        1. Configure filters (checkboxes, date range)
        2. Click 查询
        3. Extract all pages of data
        4. Save to database

        Returns:
            Result dictionary with extracted data
        """
        logger.info(f"Starting 权益包售卖汇总表 crawl: {self.target_date} to {self.end_date}")

        try:
            # Step 1: Configure filters (unless skip_navigation)
            if self.skip_navigation:
                logger.info("SKIP_NAVIGATION: Using current page state")
                state = await self._get_filter_state()
                logger.info(f"Current filter state: {state}")
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
                save_stats = self.db.save_equity_package_sales(all_data)
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
        1. Check 汇总项 checkboxes (门店, 日期)
        2. Set date range
        3. Click 查询
        """
        try:
            logger.info("Configuring filters...")

            # Ensure both checkboxes are checked
            await self._ensure_checkboxes_checked()
            await asyncio.sleep(0.5)

            # Set date range
            logger.info(f"Setting date range: {self.target_date} to {self.end_date}")
            await self._set_date_range(self.target_date, self.end_date)
            await asyncio.sleep(0.5)

            # Click query button
            logger.info("Clicking 查询")
            query_clicked = await self.frame.evaluate('''() => {
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
                logger.warning("Could not find 查询 button")
                return False

            # Wait for results
            await asyncio.sleep(5)

            # Re-acquire iframe (may have refreshed)
            self.frame = await self.get_iframe('crm-smart')
            await asyncio.sleep(1)

            return True

        except Exception as e:
            logger.error(f"Filter configuration failed: {e}")
            return False

    async def _get_filter_state(self) -> Dict[str, Any]:
        """Get current filter state for debugging."""
        try:
            return await self.frame.evaluate('''() => {
                const checkboxes = document.querySelectorAll('.el-checkbox');
                const cbState = [];
                for (const cb of checkboxes) {
                    cbState.push({
                        text: cb.textContent?.trim(),
                        isChecked: cb.classList.contains('is-checked')
                    });
                }

                const startDate = document.querySelector('input[placeholder="开始日期"]')?.value;
                const endDate = document.querySelector('input[placeholder="结束日期"]')?.value;

                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条/);

                return {
                    checkboxes: cbState,
                    dates: { start: startDate, end: endDate },
                    totalRecords: totalMatch ? totalMatch[0] : 'not found'
                };
            }''')
        except Exception as e:
            return {"error": str(e)}

    async def _ensure_checkboxes_checked(self) -> None:
        """Ensure 门店 and 日期 checkboxes are checked."""
        try:
            result = await self.frame.evaluate('''() => {
                const results = [];
                const checkboxes = document.querySelectorAll('.el-checkbox');

                for (const cb of checkboxes) {
                    const text = cb.textContent?.trim();
                    const isChecked = cb.classList.contains('is-checked');

                    if (text === '门店' || text === '日期') {
                        if (!isChecked) {
                            cb.click();
                            results.push({ text, action: 'clicked' });
                        } else {
                            results.push({ text, action: 'already_checked' });
                        }
                    }
                }
                return results;
            }''')
            logger.info(f"Checkboxes: {result}")
        except Exception as e:
            logger.warning(f"Error configuring checkboxes: {e}")

    async def _set_date_range(self, start_date: str, end_date: str) -> None:
        """Set date range using direct input."""
        try:
            # Set START date
            start_input = self.frame.locator('input[placeholder="开始日期"]')
            await start_input.click()
            await asyncio.sleep(0.5)
            await start_input.press('Meta+a')
            await asyncio.sleep(0.2)
            await start_input.press('Control+a')
            await asyncio.sleep(0.2)
            await start_input.fill(start_date)
            await asyncio.sleep(0.5)
            await start_input.press('Enter')
            await asyncio.sleep(0.5)
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)

            # Set END date
            end_input = self.frame.locator('input[placeholder="结束日期"]')
            await end_input.click()
            await asyncio.sleep(0.5)
            await end_input.press('Meta+a')
            await asyncio.sleep(0.2)
            await end_input.press('Control+a')
            await asyncio.sleep(0.2)
            await end_input.fill(end_date)
            await asyncio.sleep(0.5)
            await end_input.press('Enter')
            await asyncio.sleep(0.5)
            await self.page.keyboard.press('Escape')

        except Exception as e:
            logger.error(f"Error setting date range: {e}")

    async def _get_pagination_info(self) -> Dict[str, Any]:
        """Get pagination information."""
        try:
            info = await self.frame.evaluate('''() => {
                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条/);
                const totalRecords = totalMatch ? parseInt(totalMatch[1]) : 0;

                const pageInput = document.querySelector('input[type="number"]');
                let totalPages = 1;
                let currentPage = 1;

                if (pageInput) {
                    totalPages = parseInt(pageInput.max || '1');
                    currentPage = parseInt(pageInput.value || '1');
                }

                return {
                    total_records: totalRecords,
                    total_pages: totalPages,
                    current_page: currentPage,
                    per_page: 10
                };
            }''')
            logger.info(f"Pagination: {info['total_records']} records, {info['total_pages']} pages")
            return info
        except Exception as e:
            logger.warning(f"Error getting pagination: {e}")
            return {"total_records": 0, "total_pages": 1, "current_page": 1, "per_page": 10}

    async def _extract_table_data(self) -> List[Dict[str, Any]]:
        """Extract data from current page's table."""
        try:
            data = await self.frame.evaluate('''() => {
                const rows = [];
                let tableRows = null;

                // Try specific table structures
                const antTable = document.querySelector('.ant-table-tbody');
                if (antTable) {
                    tableRows = antTable.querySelectorAll('tr');
                }

                if (!tableRows || tableRows.length === 0) {
                    const saasTable = document.querySelector('.saas-v5-table-tbody');
                    if (saasTable) {
                        tableRows = saasTable.querySelectorAll('tr');
                    }
                }

                if (!tableRows || tableRows.length === 0) {
                    const genericTable = document.querySelector('table tbody');
                    if (genericTable) {
                        tableRows = genericTable.querySelectorAll('tr');
                    }
                }

                if (tableRows && tableRows.length > 0) {
                    for (const tr of tableRows) {
                        const cells = tr.querySelectorAll('td');
                        if (cells.length >= 9) {
                            const firstCell = cells[0]?.textContent?.trim();
                            if (!firstCell || firstCell === '序号') continue;

                            const offset = cells.length === 10 ? 1 : 0;
                            rows.push({
                                org_code: cells[offset]?.textContent?.trim() || '',
                                store_name: cells[offset + 1]?.textContent?.trim() || '',
                                date: cells[offset + 2]?.textContent?.trim() || '',
                                package_name: cells[offset + 3]?.textContent?.trim() || '',
                                unit_price: cells[offset + 4]?.textContent?.trim() || '',
                                quantity_sold: cells[offset + 5]?.textContent?.trim() || '',
                                total_sales: cells[offset + 6]?.textContent?.trim() || '',
                                refund_quantity: cells[offset + 7]?.textContent?.trim() || '',
                                refund_amount: cells[offset + 8]?.textContent?.trim() || ''
                            });
                        }
                    }
                }
                return rows;
            }''')

            # Parse and validate
            parsed_data = []
            for row in data:
                try:
                    parsed_data.append({
                        'org_code': row.get('org_code', ''),
                        'store_name': row.get('store_name', ''),
                        'date': row.get('date', ''),
                        'package_name': row.get('package_name', ''),
                        'unit_price': self.parse_number(row.get('unit_price', '0')),
                        'quantity_sold': int(self.parse_number(row.get('quantity_sold', '0'))),
                        'total_sales': self.parse_number(row.get('total_sales', '0')),
                        'refund_quantity': int(self.parse_number(row.get('refund_quantity', '0'))),
                        'refund_amount': self.parse_number(row.get('refund_amount', '0'))
                    })
                except Exception as e:
                    logger.warning(f"Error parsing row: {row} - {e}")

            logger.info(f"Extracted {len(parsed_data)} records from current page")
            return parsed_data

        except Exception as e:
            logger.error(f"Error extracting table data: {e}")
            return []

    async def _go_to_page(self, target_page: int) -> bool:
        """Navigate to specific page number."""
        try:
            result = await self.frame.evaluate('''(targetPage) => {
                const pageItems = document.querySelectorAll('.el-pager li');
                for (const el of pageItems) {
                    if (el.textContent?.trim() === String(targetPage)) {
                        el.click();
                        return { success: true, method: 'click_pager' };
                    }
                }

                const pageInput = document.querySelector('input[type="number"]');
                if (pageInput) {
                    pageInput.value = targetPage;
                    pageInput.dispatchEvent(new Event('input', { bubbles: true }));
                    pageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    pageInput.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', keyCode: 13, bubbles: true
                    }));
                    return { success: true, method: 'input_number' };
                }

                return { success: false };
            }''', target_page)

            if result.get('success'):
                logger.info(f"Navigated to page {target_page}")
                await asyncio.sleep(1.5)
                return True
            return False

        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}")
            return False

    async def _extract_all_pages(self) -> List[Dict[str, Any]]:
        """Extract data from all pages."""
        all_data = []

        pagination = await self._get_pagination_info()
        total_pages = pagination.get('total_pages', 1)
        current_page = pagination.get('current_page', 1)

        # Go to page 1 if needed
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

        logger.info(f"Total records: {len(all_data)}")
        return all_data
