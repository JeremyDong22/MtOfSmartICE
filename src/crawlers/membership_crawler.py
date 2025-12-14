"""
Membership Crawler - Extracts membership card transaction data

Navigates to the membership report page and extracts:
1. Summary data (principal, bonus, total)
2. Detailed order information
"""

import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime

from src.crawlers.base_crawler import BaseCrawler
from src.config import MEITUAN_MEMBERSHIP_REPORT_URL

logger = logging.getLogger(__name__)


class MembershipCrawler(BaseCrawler):
    """
    Crawler for membership card transaction data.

    Report: 储值支付方式明细表 (Stored Value Payment Method Details)
    """

    async def crawl(self, store_id: str, store_name: str) -> Dict[str, Any]:
        """
        Execute membership data crawl for a specific store.

        Workflow:
        1. Navigate to membership report page
        2. Set date filter to target_date
        3. Select card filters (会员卡 → 山海会员)
        4. Click 查询
        5. Extract summary data
        6. Extract order details
        7. Save to database

        Args:
            store_id: Store merchant ID
            store_name: Store name

        Returns:
            Result dictionary with crawled data
        """
        logger.info(f"Starting membership crawl for {store_name} ({store_id}) on {self.target_date}")

        try:
            # Step 1: Navigate to report page
            if not await self._navigate_to_report():
                return self.create_result(False, store_id, store_name, error="Navigation failed")

            # Step 2: Get iframe
            self.frame = await self.get_iframe('crm-smart')
            await asyncio.sleep(2)

            # Step 3: Configure filters
            if not await self._configure_filters():
                return self.create_result(False, store_id, store_name, error="Filter configuration failed")

            # Step 4: Extract data
            summary_data = await self._extract_summary_data(store_id, store_name)
            order_details = await self._extract_order_details()

            # Combine data
            data = {
                "summary": summary_data,
                "orders": order_details,
                "order_count": len(order_details),
                "total_amount": sum(item.get('total', 0) for item in summary_data)
            }

            # Save to database
            if self.db:
                await self._save_to_database(store_id, store_name, data)

            logger.info(f"Successfully crawled {len(order_details)} orders for {store_name}")
            return self.create_result(True, store_id, store_name, data=data)

        except Exception as e:
            logger.error(f"Crawl failed for {store_name}: {e}", exc_info=True)
            return self.create_result(False, store_id, store_name, error=str(e))

    async def _navigate_to_report(self) -> bool:
        """Navigate to membership report page."""
        try:
            logger.info(f"Navigating to: {MEITUAN_MEMBERSHIP_REPORT_URL}")
            await self.page.goto(MEITUAN_MEMBERSHIP_REPORT_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)
            await self.dismiss_popups()
            logger.info("Successfully navigated to report page")
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    async def _configure_filters(self) -> bool:
        """
        Configure report filters:
        1. Select "日期" dimension
        2. Expand filters
        3. Set date range
        4. Select 会员卡 → 山海会员
        5. Click 查询
        """
        try:
            # Step 1: Select 日期 dimension
            logger.info("Selecting 日期 dimension")
            date_radio = await self.frame.query_selector('.saas-radio-button-wrapper:has-text("日期")')
            if date_radio:
                await date_radio.click()
            else:
                await self.safe_evaluate('''() => {
                    const wrappers = document.querySelectorAll('.saas-radio-button-wrapper');
                    for (const w of wrappers) {
                        if (w.textContent.includes('日期')) {
                            w.click();
                            return true;
                        }
                    }
                }''')
            await asyncio.sleep(1)

            # Step 2: Expand filters
            logger.info("Expanding filters")
            expand_clicked = await self.safe_evaluate('''() => {
                const btns = document.querySelectorAll('button, span');
                for (const b of btns) {
                    if (b.textContent.includes('展开筛选')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }''')
            if expand_clicked:
                await asyncio.sleep(2)

            # Step 3: Set date range (both start and end = target_date for daily crawl)
            logger.info(f"Setting date filter to {self.target_date}")
            await self.set_date_filter(self.target_date, self.target_date)

            # Step 4: Set card type filters
            logger.info("Setting card type filters")
            await self._set_card_filters()

            # Step 5: Click query button
            logger.info("Clicking 查询 button")
            query_btn = await self.frame.query_selector('button:has-text("查询")')
            if query_btn:
                await query_btn.click()
            else:
                await self.safe_evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.includes('查询')) {
                            b.click();
                            return true;
                        }
                    }
                }''')

            await asyncio.sleep(5)  # Wait for results
            logger.info("Filter configuration complete")
            return True

        except Exception as e:
            logger.error(f"Filter configuration failed: {e}")
            return False

    async def _set_card_filters(self) -> None:
        """Set card category and type filters."""
        try:
            # Find first tree-select (卡种类)
            selectors = await self.frame.query_selector_all('.saas-select.saas-tree-select')
            logger.info(f"Found {len(selectors)} tree-select elements")

            if len(selectors) >= 1:
                # Click first selector
                await selectors[0].click()
                await asyncio.sleep(1)

                # Select 会员卡
                selected = await self.safe_evaluate('''() => {
                    const nodes = document.querySelectorAll('.saas-select-tree-treenode');
                    for (const node of nodes) {
                        if (node.textContent.includes('会员卡') && !node.textContent.includes('匿名')) {
                            node.click();
                            return true;
                        }
                    }
                    return false;
                }''')

                if selected:
                    logger.info("Selected 会员卡")
                    await asyncio.sleep(1)
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(2)

                    # Now find second selector (卡类型)
                    selectors2 = await self.frame.query_selector_all('.saas-select.saas-tree-select')
                    logger.info(f"Found {len(selectors2)} tree-select elements after selecting 会员卡")

                    if len(selectors2) >= 2:
                        await selectors2[1].click()
                        await asyncio.sleep(1)

                        # Select 山海会员
                        selected2 = await self.safe_evaluate('''() => {
                            const nodes = document.querySelectorAll('.saas-select-tree-treenode');
                            for (const node of nodes) {
                                if (node.textContent.includes('山海会员')) {
                                    node.click();
                                    return true;
                                }
                            }
                            return false;
                        }''')

                        if selected2:
                            logger.info("Selected 山海会员")

                        await self.page.keyboard.press('Escape')
                        await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Error setting card filters: {e}")

    async def _extract_summary_data(self, store_id: str, store_name: str) -> List[Dict]:
        """Extract summary data from main table."""
        try:
            logger.info("Extracting summary data")

            # Check for no data
            no_data = await self.frame.query_selector(':has-text("暂无数据")')
            if no_data:
                logger.warning("No data available")
                return []

            # Extract table data
            table_data = await self.safe_evaluate('''() => {
                const rows = [];
                const tbody = document.querySelector('.saas-v5-table-tbody');
                if (!tbody) return rows;

                const trs = tbody.querySelectorAll('tr:not(.saas-v5-table-measure-row)');
                for (const tr of trs) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length > 9) {
                        const firstCell = cells[0]?.innerText?.trim();
                        if (firstCell === '合计') continue;

                        rows.push({
                            store: cells[1]?.innerText?.trim() || '',
                            principal: cells[7]?.innerText?.trim() || '0',
                            bonus: cells[8]?.innerText?.trim() || '0',
                            total: cells[9]?.innerText?.trim() || '0'
                        });
                    }
                }
                return rows;
            }''', [])

            # Parse data
            summary = []
            for row in table_data:
                summary.append({
                    "store": row.get('store', store_name),
                    "merchant_id": store_id,
                    "principal": self.parse_number(row.get('principal', '0')),
                    "bonus": self.parse_number(row.get('bonus', '0')),
                    "total": self.parse_number(row.get('total', '0')),
                    "card_type": "山海会员"
                })

            logger.info(f"Extracted {len(summary)} summary records")
            return summary

        except Exception as e:
            logger.error(f"Error extracting summary data: {e}")
            return []

    async def _extract_order_details(self) -> List[Dict]:
        """Extract detailed order information."""
        all_orders = []

        try:
            # Find and click "查看订单明细" buttons
            detail_btns = await self.frame.query_selector_all('button:has-text("查看订单明细")')
            logger.info(f"Found {len(detail_btns)} detail buttons")

            for idx, btn in enumerate(detail_btns):
                try:
                    await btn.click()
                    logger.info(f"Clicked detail button {idx + 1}")
                    await asyncio.sleep(2)

                    # Extract from dialog
                    orders = await self._extract_dialog_orders()
                    all_orders.extend(orders)

                    # Close dialog
                    close_btn = await self.frame.query_selector('button.saas-modal-close, [aria-label="Close"]')
                    if close_btn:
                        await close_btn.click()
                    else:
                        await self.page.keyboard.press('Escape')

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.warning(f"Error extracting detail {idx + 1}: {e}")
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error extracting order details: {e}")

        logger.info(f"Extracted {len(all_orders)} total orders")
        return all_orders

    async def _extract_dialog_orders(self) -> List[Dict]:
        """Extract orders from detail dialog with pagination."""
        all_orders = []

        try:
            while True:
                # Extract current page
                page_data = await self.safe_evaluate('''() => {
                    const orders = [];
                    const dialog = document.querySelector('.saas-modal, [role="dialog"]');
                    if (!dialog) return { orders: [], hasNext: false };

                    const rows = dialog.querySelectorAll('.saas-v5-table-tbody tr, table tbody tr');
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 6) {
                            const orderNum = cells[1]?.innerText?.trim() || '';
                            if (orderNum.startsWith('HY')) {
                                orders.push({
                                    order_number: orderNum,
                                    order_time: cells[2]?.innerText?.trim() || '',
                                    order_status: cells[3]?.innerText?.trim() || '',
                                    order_source: cells[4]?.innerText?.trim() || '',
                                    principal: cells[5]?.innerText?.trim() || '0',
                                    bonus: cells[6]?.innerText?.trim() || '0',
                                    deposit: cells[7]?.innerText?.trim() || '0',
                                    phone: cells[8]?.innerText?.trim() || '',
                                    card_number: cells[9]?.innerText?.trim() || ''
                                });
                            }
                        }
                    }

                    // Check for next page
                    const nextBtn = dialog.querySelector('li.saas-pagination-next button:not([disabled])');
                    return { orders: orders, hasNext: nextBtn !== null };
                }''', {"orders": [], "hasNext": False})

                # Process orders
                for order in page_data.get('orders', []):
                    all_orders.append({
                        'order_number': order.get('order_number'),
                        'order_time': order.get('order_time'),
                        'order_status': order.get('order_status'),
                        'order_source': order.get('order_source'),
                        'principal': self.parse_number(order.get('principal', '0')),
                        'bonus': self.parse_number(order.get('bonus', '0')),
                        'deposit': self.parse_number(order.get('deposit', '0')),
                        'phone': order.get('phone'),
                        'card_number': order.get('card_number'),
                        'card_type': '山海会员'
                    })

                # Check if more pages
                if not page_data.get('hasNext', False):
                    break

                # Click next page
                next_clicked = await self.safe_evaluate('''() => {
                    const dialog = document.querySelector('.saas-modal, [role="dialog"]');
                    if (!dialog) return false;
                    const nextBtn = dialog.querySelector('li.saas-pagination-next button:not([disabled])');
                    if (nextBtn) {
                        nextBtn.click();
                        return true;
                    }
                    return false;
                }''')

                if not next_clicked:
                    break

                await asyncio.sleep(1.5)

        except Exception as e:
            logger.error(f"Error extracting dialog orders: {e}")

        return all_orders

    async def _save_to_database(self, store_id: str, store_name: str, data: Dict) -> None:
        """Save crawled data to database."""
        try:
            if not self.db:
                return

            summary = data.get('summary', [])
            orders = data.get('orders', [])

            # Calculate totals
            total_amount = sum(item.get('total', 0) for item in summary)
            cards_opened = len(orders)

            # Save membership data
            self.db.save_membership_data(
                store_id=store_id,
                store_name=store_name,
                date=self.target_date,
                cards_opened=cards_opened,
                total_amount=total_amount,
                card_details=orders
            )

            # Log crawl
            self.db.log_crawl(
                store_id=store_id,
                crawler_type="membership_card",
                date=self.target_date,
                status="success",
                records_count=len(orders)
            )

            logger.info(f"Saved {len(orders)} orders to database")

        except Exception as e:
            logger.error(f"Error saving to database: {e}")
