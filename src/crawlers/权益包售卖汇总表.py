"""
权益包售卖汇总表 Crawler - Extracts equity package sales data from aggregated group account
v2.0 - Updated to use conditional duplicate handling (only updates if values are higher)

This crawler is designed for 集团账号 (group account) that aggregates all stores.
Unlike the per-store MembershipCrawler, this crawler:
1. Starts from selectorg page (https://pos.meituan.com/web/rms-account#/selectorg)
2. Selects 集团 (group) account
3. Navigates to 营销中心 → 数据报表 → 权益包售卖汇总表
4. Configures filters (门店, 日期 checkboxes, date range)
5. Extracts data for ALL stores in one table with pagination

Report URL: https://pos.meituan.com/web/marketing/crm/report/right-package
Iframe URL: https://pos.meituan.com/web/crm-smart/report/right-package
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

# URLs for navigation
SELECTORG_URL = "https://pos.meituan.com/web/rms-account#/selectorg"
MARKETING_CENTER_URL = "https://pos.meituan.com/web/marketing/home#/rms-discount/marketing"
REPORT_URL = "https://pos.meituan.com/web/marketing/crm/report/right-package"


class EquityPackageSalesCrawler(BaseCrawler):
    """
    Crawler for 权益包售卖汇总表 (Equity Package Sales Summary).

    This crawler works with 集团账号 (group account) to extract sales data
    for all stores in a single crawl, avoiding the need for per-store switching.

    Data extracted per row:
    - 机构编码 (org_code): Store code (e.g., MD00007)
    - 售卖门店 (store_name): Store name
    - 日期 (date): Business date
    - 权益包名称 (package_name): Package name (e.g., 山海会员)
    - 售卖单价 (unit_price): Unit price
    - 售卖数量 (quantity_sold): Quantity sold
    - 售卖总价 (total_sales): Total sales amount
    - 退款数量 (refund_quantity): Refund quantity
    - 退款总价 (refund_amount): Refund amount
    """

    def __init__(self, page, frame, db_manager, target_date: str, end_date: str = None, skip_navigation: bool = False):
        """
        Initialize the crawler.

        Args:
            page: Playwright page object
            frame: The iframe (will be re-acquired during crawl)
            db_manager: Database manager instance
            target_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (defaults to target_date)
            skip_navigation: If True, skip page navigation and use current page state
                             (useful when page is already configured via DevTools)
        """
        super().__init__(page, frame, db_manager, target_date)
        self.end_date = end_date or target_date
        self.group_merchant_id = None  # Will be set after selecting group
        self.skip_navigation = skip_navigation

    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        """
        Execute the crawl for aggregated group account.

        Note: store_id and store_name are optional since this crawler
        works with the group account, not individual stores.

        Workflow:
        1. Navigate to selectorg page
        2. Select 集团 (group) account
        3. Navigate to 营销中心 → 数据报表 → 权益包售卖汇总表
        4. Configure filters (汇总项 checkboxes, date range)
        5. Click 查询
        6. Extract all pages of data

        Returns:
            Result dictionary with all extracted data
        """
        logger.info(f"Starting 权益包售卖汇总表 crawl for date range: {self.target_date} to {self.end_date}")
        logger.info(f"Skip navigation mode: {self.skip_navigation}")

        try:
            # Step 1: Navigate to report page (unless skip_navigation is True)
            if self.skip_navigation:
                logger.info("SKIP_NAVIGATION mode: Using current page state without navigation")
            elif not await self._navigate_to_report():
                return self.create_result(False, store_id or "GROUP", store_name or "集团",
                                         error="Navigation to report failed")

            # Step 2: Get iframe - with detailed frame debugging
            logger.info(f"Main page URL: {self.page.url}")
            logger.info(f"Total frames in page: {len(self.page.frames)}")
            for i, f in enumerate(self.page.frames):
                logger.info(f"  Frame {i}: {f.url}")

            self.frame = await self.get_iframe('crm-smart')
            logger.info(f"Selected frame URL: {self.frame.url if hasattr(self.frame, 'url') else 'N/A'}")
            await asyncio.sleep(2)

            # Debug: Dump what Playwright sees in the frame
            try:
                frame_text = await self.frame.inner_text('body')
                logger.info(f"Frame body text (first 500 chars): {frame_text[:500] if frame_text else 'EMPTY'}")

                # Check specific elements
                debug_result = await self.frame.evaluate('''() => {
                    return {
                        bodyHTML: document.body?.innerHTML?.substring(0, 300) || 'NO BODY',
                        title: document.title,
                        allElementsCount: document.querySelectorAll('*').length,
                        checkboxInputs: document.querySelectorAll('input[type="checkbox"]').length,
                        elCheckbox: document.querySelectorAll('.el-checkbox').length,
                        buttons: Array.from(document.querySelectorAll('button')).map(b => b.textContent?.trim()).slice(0, 5)
                    };
                }''')
                logger.info(f"Frame debug: {debug_result}")
            except Exception as e:
                logger.error(f"Frame debug error: {e}")

            # Step 3: Configure filters (skip in skip_navigation mode - page already configured)
            if self.skip_navigation:
                logger.info("SKIP_NAVIGATION mode: Skipping filter configuration, using current state")
                # Just get filter state for debugging
                state = await self._get_filter_state()
                logger.info(f"Current filter state: {state}")
            elif not await self._configure_filters():
                return self.create_result(False, store_id or "GROUP", store_name or "集团",
                                         error="Filter configuration failed")

            # Step 4: Extract all data with pagination
            all_data = await self._extract_all_pages()

            # Step 5: Get pagination info for summary
            pagination_info = await self._get_pagination_info()

            # Step 6: Save to database with conditional duplicate handling
            save_stats = {"inserted": 0, "updated": 0, "skipped": 0}
            if all_data:
                save_stats = self.db.save_equity_package_sales(all_data)
                logger.info(
                    f"Database save complete: {save_stats['inserted']} inserted, "
                    f"{save_stats['updated']} updated, {save_stats['skipped']} skipped"
                )

            # Prepare result
            data = {
                "records": all_data,
                "record_count": len(all_data),
                "save_stats": save_stats,  # Include save statistics
                "date_range": {
                    "start": self.target_date,
                    "end": self.end_date
                },
                "pagination": pagination_info
            }

            logger.info(f"Successfully extracted {len(all_data)} records")
            return self.create_result(True, store_id or "GROUP", store_name or "集团", data=data)

        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
            return self.create_result(False, store_id or "GROUP", store_name or "集团", error=str(e))

    async def _navigate_to_report(self) -> bool:
        """
        Navigate to 权益包售卖汇总表 report page.

        Workflow:
        1. Navigate to selectorg page
        2. Select 集团 (group) account
        3. Navigate to report page
        """
        try:
            # Step 1: Navigate to selectorg page first
            logger.info(f"Step 1: Navigating to selectorg page: {SELECTORG_URL}")
            await self.page.goto(SELECTORG_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(2)

            # Step 2: Select 集团 account
            logger.info("Step 2: Selecting 集团 (group) account...")
            if not await self._select_group_account():
                logger.error("Failed to select 集团 account")
                return False
            await asyncio.sleep(3)

            # Step 3: Navigate to report page
            logger.info(f"Step 3: Navigating to report page: {REPORT_URL}")
            await self.page.goto(REPORT_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)

            # Wait for iframe to fully load
            logger.info("Waiting for iframe content to load...")
            await asyncio.sleep(2)

            # Dismiss any popups
            await self.dismiss_popups()

            # Verify we're on the right page
            current_url = self.page.url
            if 'right-package' not in current_url:
                logger.warning(f"Unexpected URL: {current_url}")
                return False

            logger.info("Successfully navigated to 权益包售卖汇总表")

            # Get iframe and check if we need to switch to new version
            self.frame = await self.get_iframe('crm-smart')
            await asyncio.sleep(1)

            # Check for "切换新版" button (means we're on old version)
            needs_switch = await self.frame.evaluate('''() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.includes('切换新版')) {
                        return true;
                    }
                }
                return false;
            }''')

            if needs_switch:
                logger.info("Detected old version, clicking '切换新版' to switch...")
                await self.frame.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.textContent.includes('切换新版')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                # Wait for new version to load
                await asyncio.sleep(3)
                # Re-acquire iframe after switch
                self.frame = await self.get_iframe('crm-smart')
                await asyncio.sleep(1)
                logger.info("Switched to new version")

            return True

        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    async def _select_group_account(self) -> bool:
        """
        Select 集团 (group) account from the selectorg page.

        The selectorg page shows a list of organizations including 集团.
        We need to click the "选 择" button next to 集团.
        """
        try:
            # Wait for the page to fully load
            await asyncio.sleep(1)

            # Find and click the 集团 "选 择" button
            # The structure is: button containing "集团" text, with a child "选 择" button
            result = await self.page.evaluate('''() => {
                // Find all buttons that contain "选 择"
                const allButtons = document.querySelectorAll('button');

                // First, find the 集团 section by looking for text containing "集团"
                const allText = document.body.innerText;
                if (!allText.includes('集团')) {
                    return { success: false, reason: 'no_group_text_found' };
                }

                // Find the expandable button for 集团 (it has "集团" in its text)
                let groupButton = null;
                for (const btn of allButtons) {
                    const text = btn.textContent || '';
                    if (text.includes('集团') && text.includes('选 择')) {
                        // This is the group button container, find the inner "选 择" button
                        const selectBtn = btn.querySelector('button');
                        if (selectBtn && selectBtn.textContent.includes('选 择')) {
                            selectBtn.click();
                            return { success: true, method: 'inner_select_button' };
                        }
                        // Or the button itself might be the select button
                        if (text.trim().endsWith('选 择')) {
                            btn.click();
                            return { success: true, method: 'group_button_direct' };
                        }
                    }
                }

                // Alternative: Find "选 择" buttons and check their parent for "集团"
                for (const btn of allButtons) {
                    if (btn.textContent?.trim() === '选 择') {
                        // Check parent elements for "集团" text
                        let parent = btn.parentElement;
                        for (let i = 0; i < 5 && parent; i++) {
                            const parentText = parent.textContent || '';
                            if (parentText.includes('集团') && parentText.includes('GP')) {
                                btn.click();
                                return { success: true, method: 'parent_search' };
                            }
                            parent = parent.parentElement;
                        }
                    }
                }

                return { success: false, reason: 'group_select_button_not_found' };
            }''')

            if result.get('success'):
                logger.info(f"Successfully clicked 集团 select button via {result.get('method')}")
                return True
            else:
                logger.error(f"Failed to select 集团: {result.get('reason')}")
                return False

        except Exception as e:
            logger.error(f"Error selecting group account: {e}")
            return False

    async def _configure_filters(self) -> bool:
        """
        Configure report filters:
        1. Check both 汇总项 checkboxes (门店, 日期)
        2. Set date range
        3. Click 查询
        """
        try:
            # Debug: Log current state before configuration
            state_before = await self._get_filter_state()
            logger.info(f"Filter state BEFORE configuration: {state_before}")

            # Step 1: Ensure both checkboxes are checked
            logger.info("Configuring 汇总项 checkboxes")
            await self._ensure_checkboxes_checked()
            await asyncio.sleep(0.5)

            # Step 2: Set date range using direct input method
            logger.info(f"Setting date range: {self.target_date} to {self.end_date}")
            await self._set_date_range_direct(self.target_date, self.end_date)
            await asyncio.sleep(0.5)

            # Debug: Log state after configuration
            state_after = await self._get_filter_state()
            logger.info(f"Filter state AFTER configuration: {state_after}")

            # Step 3: Click query button
            logger.info("Clicking 查询 button")
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

            # Wait for data to load - need longer wait for query results
            logger.info("Waiting for query results...")
            await asyncio.sleep(5)

            # Re-acquire iframe reference after query (it may have refreshed)
            self.frame = await self.get_iframe('crm-smart')
            await asyncio.sleep(1)

            # Debug: Log state after query
            state_final = await self._get_filter_state()
            logger.info(f"Filter state AFTER query: {state_final}")

            logger.info("Filter configuration complete")
            return True

        except Exception as e:
            logger.error(f"Filter configuration failed: {e}")
            return False

    async def _get_filter_state(self) -> Dict[str, Any]:
        """
        Get current filter state for debugging.
        """
        try:
            return await self.frame.evaluate('''() => {
                // Get checkboxes state (Element UI structure)
                const checkboxes = document.querySelectorAll('.el-checkbox');
                const cbState = [];
                for (const cb of checkboxes) {
                    cbState.push({
                        text: cb.textContent?.trim(),
                        isChecked: cb.classList.contains('is-checked')
                    });
                }

                // Get date inputs
                const startDate = document.querySelector('input[placeholder="开始日期"]')?.value;
                const endDate = document.querySelector('input[placeholder="结束日期"]')?.value;

                // Get total records text
                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条/);

                return {
                    checkboxes: cbState,
                    dates: { start: startDate, end: endDate },
                    totalRecords: totalMatch ? totalMatch[0] : 'not found'
                };
            }''')
        except Exception as e:
            logger.warning(f"Error getting filter state: {e}")
            return {"error": str(e)}

    async def _ensure_checkboxes_checked(self) -> None:
        """
        Ensure both 汇总项 checkboxes (门店, 日期) are checked.
        Uses Element UI checkbox structure (.el-checkbox wrapper).
        """
        try:
            result = await self.frame.evaluate('''() => {
                const results = [];
                // Element UI checkboxes: .el-checkbox wrapper with .is-checked class when checked
                const checkboxes = document.querySelectorAll('.el-checkbox');

                for (const cb of checkboxes) {
                    const text = cb.textContent?.trim();
                    const isChecked = cb.classList.contains('is-checked');

                    // Only process 门店 and 日期 checkboxes
                    if (text === '门店' || text === '日期') {
                        if (!isChecked) {
                            // Click the checkbox wrapper to toggle
                            cb.click();
                            results.push({ text, action: 'clicked', wasChecked: false });
                        } else {
                            results.push({ text, action: 'already_checked', wasChecked: true });
                        }
                    }
                }

                return results;
            }''')
            logger.info(f"Checkboxes configured: {result}")
        except Exception as e:
            logger.warning(f"Error configuring checkboxes: {e}")

    async def _set_date_range_direct(self, start_date: str, end_date: str) -> None:
        """
        Set date range by clicking input, clearing, and typing new date.

        Uses Playwright's native input handling with sufficient delays for
        the date picker to properly register changes.
        """
        try:
            # Set START date
            logger.info(f"Setting start date to: {start_date}")
            start_input = self.frame.locator('input[placeholder="开始日期"]')

            # Click to focus and open date picker
            await start_input.click()
            await asyncio.sleep(0.5)

            # Select all and type new value
            await start_input.press('Meta+a')  # macOS: Cmd+A
            await asyncio.sleep(0.2)
            await start_input.press('Control+a')  # Windows/Linux: Ctrl+A
            await asyncio.sleep(0.2)
            await start_input.fill(start_date)
            await asyncio.sleep(0.5)

            # Press Enter to confirm the date
            await start_input.press('Enter')
            await asyncio.sleep(0.5)

            # Close any popup
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)

            # Set END date
            logger.info(f"Setting end date to: {end_date}")
            end_input = self.frame.locator('input[placeholder="结束日期"]')

            # Click to focus and open date picker
            await end_input.click()
            await asyncio.sleep(0.5)

            # Select all and type new value
            await end_input.press('Meta+a')  # macOS: Cmd+A
            await asyncio.sleep(0.2)
            await end_input.press('Control+a')  # Windows/Linux: Ctrl+A
            await asyncio.sleep(0.2)
            await end_input.fill(end_date)
            await asyncio.sleep(0.5)

            # Press Enter to confirm the date
            await end_input.press('Enter')
            await asyncio.sleep(0.5)

            # Close any popup
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)

            # Verify the values were set
            state = await self._get_filter_state()
            logger.info(f"Date range set: {state.get('dates', {})}")

        except Exception as e:
            logger.error(f"Error setting date range: {e}")

    async def _get_pagination_info(self) -> Dict[str, Any]:
        """
        Get pagination information from the page.

        Uses input[type="number"] (el-input__inner) for page navigation.
        """
        try:
            info = await self.frame.evaluate('''() => {
                // Get total records from "共 X 条" text
                const allText = document.body.innerText;
                const totalMatch = allText.match(/共\\s*(\\d+)\\s*条/);
                const totalRecords = totalMatch ? parseInt(totalMatch[1]) : 0;

                // Get page input - it's input[type="number"] with el-input__inner class
                // This is the "前往 X 页" input
                const pageInput = document.querySelector('input[type="number"]') ||
                                  document.querySelector('input.el-input__inner[type="number"]') ||
                                  document.querySelector('input[role="spinbutton"]');

                let totalPages = 1;
                let currentPage = 1;

                if (pageInput) {
                    // max attribute contains total pages
                    totalPages = parseInt(pageInput.max || '1');
                    currentPage = parseInt(pageInput.value || '1');
                } else {
                    // Fallback: count page number links
                    const pageLinks = document.querySelectorAll('.el-pager li, .ant-pagination-item');
                    if (pageLinks.length > 0) {
                        totalPages = pageLinks.length;
                        const activePage = document.querySelector('.el-pager .active, .ant-pagination-item-active');
                        currentPage = activePage ? parseInt(activePage.textContent) : 1;
                    }
                }

                return {
                    total_records: totalRecords,
                    total_pages: totalPages,
                    current_page: currentPage,
                    per_page: 10,
                    debug: {
                        matchText: totalMatch ? totalMatch[0] : 'not found',
                        pageInputFound: !!pageInput,
                        pageInputMax: pageInput?.max,
                        pageInputValue: pageInput?.value,
                        url: document.location.href
                    }
                };
            }''')

            logger.info(f"Pagination debug: {info.get('debug', {})}")

            logger.info(f"Pagination: {info['total_records']} records, {info['total_pages']} pages")
            return info

        except Exception as e:
            logger.warning(f"Error getting pagination info: {e}")
            return {"total_records": 0, "total_pages": 1, "current_page": 1, "per_page": 10}

    async def _extract_table_data(self) -> List[Dict[str, Any]]:
        """
        Extract data from the current page's table.
        Uses DOM-based approach to find table rows.
        v1.6: Fixed selector to avoid duplicate row extraction.
        """
        try:
            data = await self.frame.evaluate('''() => {
                const rows = [];

                // Method 1: Try specific table structure (check in order of specificity)
                // IMPORTANT: Use only ONE selector to avoid duplicate matches
                let tableRows = null;

                // Check for Ant Design table first
                const antTable = document.querySelector('.ant-table-tbody');
                if (antTable) {
                    tableRows = antTable.querySelectorAll('tr');
                }

                // Check for SaaS v5 table
                if (!tableRows || tableRows.length === 0) {
                    const saasTable = document.querySelector('.saas-v5-table-tbody');
                    if (saasTable) {
                        tableRows = saasTable.querySelectorAll('tr');
                    }
                }

                // Fallback to generic tbody (only if no specific table found)
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
                            // Skip header row or empty rows
                            const firstCell = cells[0]?.textContent?.trim();
                            if (!firstCell || firstCell === '序号') continue;

                            // Extract cell values (skip 序号 column if present)
                            // Columns: 序号(0), 机构编码(1), 售卖门店(2), 日期(3), 权益包名称(4),
                            //          售卖单价(5), 售卖数量(6), 售卖总价(7), 退款数量(8), 退款总价(9)
                            const offset = cells.length === 10 ? 1 : 0;  // Has 序号 column
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

                // Method 2: If DOM method fails, try text-based extraction
                if (rows.length === 0) {
                    // Find all text nodes that match MD code pattern
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );

                    const textNodes = [];
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text && text.length < 100) {
                            textNodes.push(text);
                        }
                    }

                    // Headers to skip
                    const headers = new Set([
                        '序号', '机构编码', '售卖门店', '日期', '权益包名称',
                        '售卖单价（元）', '售卖数量', '售卖总价（元）', '退款数量', '退款总价（元）'
                    ]);

                    // Find MD codes and extract following values
                    for (let i = 0; i < textNodes.length; i++) {
                        const text = textNodes[i];
                        // Match MD followed by 5 digits
                        if (/^MD\\d{5}$/.test(text)) {
                            // Collect next 8 values (store_name, date, package, price, qty, total, refund_qty, refund_amt)
                            // After MD code, ALL following values are data (don't filter numbers)
                            const rowData = [text];
                            let j = i + 1;
                            while (rowData.length < 9 && j < textNodes.length) {
                                const nextText = textNodes[j];
                                // Only skip headers, not numbers (numbers after MD code are data values)
                                if (!headers.has(nextText)) {
                                    // Stop if we hit another MD code (next row)
                                    if (/^MD\\d{5}$/.test(nextText)) break;
                                    rowData.push(nextText);
                                }
                                j++;
                            }

                            if (rowData.length >= 9) {
                                rows.push({
                                    org_code: rowData[0],
                                    store_name: rowData[1],
                                    date: rowData[2],
                                    package_name: rowData[3],
                                    unit_price: rowData[4],
                                    quantity_sold: rowData[5],
                                    total_sales: rowData[6],
                                    refund_quantity: rowData[7],
                                    refund_amount: rowData[8]
                                });
                            }
                        }
                    }
                }

                return rows;
            }''')

            # Parse and validate data
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
        """
        Navigate to a specific page by clicking its page number.

        Args:
            target_page: Page number to navigate to (1-indexed)

        Returns True if successfully navigated.
        """
        try:
            result = await self.frame.evaluate('''(targetPage) => {
                // Method 1: Click on page number element in pagination
                // Look for el-pager (Element UI) or ant-pagination page numbers
                const pageItems = document.querySelectorAll('.el-pager li, .ant-pagination-item, [class*="pagination"] li');
                for (const el of pageItems) {
                    const text = el.textContent?.trim();
                    if (text === String(targetPage)) {
                        el.click();
                        return { success: true, method: 'click_pager', page: targetPage };
                    }
                }

                // Method 2: Use the page number input (input[type="number"])
                const pageInput = document.querySelector('input[type="number"]') ||
                                  document.querySelector('input.el-input__inner[type="number"]');
                if (pageInput) {
                    pageInput.value = targetPage;
                    pageInput.dispatchEvent(new Event('input', { bubbles: true }));
                    pageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    // Press Enter to confirm navigation
                    pageInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                    return { success: true, method: 'input_number', page: targetPage };
                }

                // Method 3: Try clicking any element with the target page number
                const allElements = document.querySelectorAll('li, a, span, button');
                for (const el of allElements) {
                    const text = el.textContent?.trim();
                    if (text === String(targetPage) && el.closest('[class*="pagination"]')) {
                        el.click();
                        return { success: true, method: 'click_any', page: targetPage };
                    }
                }

                return { success: false, reason: 'page_number_not_found' };
            }''', target_page)

            if result.get('success'):
                logger.info(f"Navigated to page {target_page} via {result.get('method')}")
                await asyncio.sleep(1.5)  # Wait for page to load
                return True
            else:
                logger.warning(f"Could not navigate to page {target_page}: {result.get('reason')}")
                return False

        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}")
            return False

    async def _click_next_page(self) -> bool:
        """
        Click the next page button.

        Returns True if successfully clicked, False if no next page.
        """
        try:
            # Get current page info
            pagination = await self._get_pagination_info()
            current_page = pagination.get('current_page', 1)
            total_pages = pagination.get('total_pages', 1)

            if current_page >= total_pages:
                logger.info(f"Already on last page ({current_page}/{total_pages})")
                return False

            # Navigate to next page
            return await self._go_to_page(current_page + 1)

        except Exception as e:
            logger.error(f"Error clicking next page: {e}")
            return False

    async def _extract_all_pages(self) -> List[Dict[str, Any]]:
        """
        Extract data from all pages.
        Navigates to page 1 first, then extracts all pages sequentially.
        """
        all_data = []

        # Get pagination info first
        pagination = await self._get_pagination_info()
        total_pages = pagination.get('total_pages', 1)
        current_page = pagination.get('current_page', 1)

        logger.info(f"Pagination: {pagination['total_records']} records, {total_pages} pages, current page: {current_page}")

        # Navigate to page 1 if not already there
        if current_page != 1:
            logger.info("Navigating to page 1 first...")
            await self._go_to_page(1)
            await asyncio.sleep(1)

        logger.info(f"Extracting data from {total_pages} pages...")

        for page_num in range(1, total_pages + 1):
            logger.info(f"Extracting page {page_num}/{total_pages}")

            # Extract current page
            page_data = await self._extract_table_data()
            logger.info(f"  Page {page_num}: found {len(page_data)} records")
            all_data.extend(page_data)

            # Navigate to next page if not last
            if page_num < total_pages:
                await self._go_to_page(page_num + 1)
                await asyncio.sleep(1)

        logger.info(f"Total records extracted: {len(all_data)}")
        return all_data
