"""
Store Navigator - Handles store selection and switching
v2.0 - Rewritten to handle the selectorg page directly

This module provides functionality to:
1. Get all available stores from the selectorg page
2. Select a store by clicking its "选 择" button
3. Navigate back to selectorg page after crawling

Page Structure on #/selectorg:
- Each store card has: 门店名称, 商户号, 机构编码, "选 择" button
- Clicking "选 择" enters that store's backend
- URL pattern: https://pos.meituan.com/web/rms-account#/selectorg
"""

import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import Page

from src.config import MEITUAN_DASHBOARD_URL, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# URL for store selection page
SELECTORG_URL = "https://pos.meituan.com/web/rms-account#/selectorg"


class StoreNavigator:
    """
    Handles store navigation and selection in the Meituan backend.

    After login, user lands on the selectorg page where all stores are listed.
    Each store has a "选 择" button to enter its backend.
    """

    def __init__(self, page: Page):
        """
        Initialize store navigator.

        Args:
            page: Playwright page object
        """
        self.page = page

    def is_on_selectorg_page(self) -> bool:
        """Check if currently on the store selection page."""
        return "#/selectorg" in self.page.url

    async def navigate_to_selectorg(self) -> bool:
        """
        Navigate to the store selection page.

        Returns:
            bool: True if navigation successful
        """
        try:
            logger.info(f"Navigating to store selection page: {SELECTORG_URL}")
            await self.page.goto(SELECTORG_URL, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(1)

            # Verify we're on the right page
            if self.is_on_selectorg_page():
                logger.info("Successfully navigated to selectorg page")
                return True
            else:
                logger.warning(f"Navigation resulted in different page: {self.page.url}")
                return False

        except Exception as e:
            logger.error(f"Failed to navigate to selectorg: {e}")
            return False

    async def navigate_to_dashboard(self) -> bool:
        """
        Navigate to the Meituan dashboard (after selecting a store).

        Returns:
            bool: True if navigation successful
        """
        try:
            logger.info(f"Navigating to dashboard: {MEITUAN_DASHBOARD_URL}")
            await self.page.goto(MEITUAN_DASHBOARD_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(2)
            logger.info(f"Successfully navigated to: {self.page.url}")
            return True

        except Exception as e:
            logger.error(f"Failed to navigate to dashboard: {e}")
            return False

    async def get_all_stores_from_selectorg(self) -> List[Dict[str, str]]:
        """
        Get all available stores from the selectorg page.

        The page lists stores with:
        - Store name (e.g., "宁桂杏山野烤肉（绵阳1958店）")
        - Merchant ID (e.g., "56756952")
        - Org code (e.g., "MD00006")
        - "选 择" button

        Returns:
            List of store dictionaries with 'store_id', 'store_name', 'org_code' keys
        """
        stores = []

        try:
            # Make sure we're on the selectorg page
            if not self.is_on_selectorg_page():
                logger.info("Not on selectorg page, navigating...")
                if not await self.navigate_to_selectorg():
                    return stores

            await asyncio.sleep(1)  # Wait for content to load

            # Extract stores from the page
            # Find all "选 择" buttons, then get nearby store info
            stores_data = await self.page.evaluate('''() => {
                const stores = [];

                // Find all "选 择" buttons
                const allButtons = document.querySelectorAll('button');
                const selectButtons = Array.from(allButtons).filter(btn =>
                    btn.textContent.trim().replace(/\\s/g, '') === '选择'
                );

                for (const btn of selectButtons) {
                    // Go up to find the store card container
                    let container = btn.parentElement;
                    for (let i = 0; i < 10 && container; i++) {
                        const text = container.textContent || '';

                        // Look for 8-digit merchant ID in this container
                        const idMatch = text.match(/\\d{8}/);
                        if (!idMatch) {
                            container = container.parentElement;
                            continue;
                        }

                        const merchantId = idMatch[0];

                        // Look for store name (contains （ and ends with 店） or 火锅）)
                        let storeName = '';
                        const allElements = container.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.children.length > 0) continue;  // Only leaf nodes
                            const elText = el.textContent?.trim() || '';
                            if ((elText.endsWith('店）') || elText.endsWith('火锅）')) &&
                                elText.includes('（') &&
                                elText.length > 5 && elText.length < 50) {
                                storeName = elText;
                                break;
                            }
                        }

                        // Look for org code (MD followed by digits)
                        let orgCode = '';
                        const codeMatch = text.match(/MD\\d+/);
                        if (codeMatch) {
                            orgCode = codeMatch[0];
                        }

                        if (storeName && merchantId) {
                            // Avoid duplicates
                            if (!stores.some(s => s.store_id === merchantId)) {
                                stores.push({
                                    store_id: merchantId,
                                    store_name: storeName,
                                    org_code: orgCode
                                });
                            }
                        }
                        break;
                    }
                }

                return stores;
            }''')

            if stores_data:
                stores = stores_data
                logger.info(f"Found {len(stores)} stores on selectorg page:")
                for store in stores:
                    logger.info(f"  - {store['store_name']} (ID: {store['store_id']}, Code: {store['org_code']})")
            else:
                logger.warning("No stores found on selectorg page")

        except Exception as e:
            logger.error(f"Error getting stores from selectorg: {e}", exc_info=True)

        return stores

    async def select_store(self, store_id: str, store_name: str = "") -> bool:
        """
        Select a store by clicking its "选 择" button on the selectorg page.

        Args:
            store_id: The merchant/store ID (e.g., "58188193")
            store_name: The store name (optional, for logging)

        Returns:
            bool: True if store was selected successfully
        """
        try:
            logger.info(f"Selecting store: {store_name or store_id}")

            # Make sure we're on the selectorg page
            if not self.is_on_selectorg_page():
                logger.info("Not on selectorg page, navigating...")
                if not await self.navigate_to_selectorg():
                    return False
                await asyncio.sleep(1)

            # Find and click the "选 择" button for this store
            # Strategy: Find the button whose container has the target merchant ID
            clicked = await self.page.evaluate('''(targetStoreId) => {
                // Find all "选 择" buttons
                const allButtons = document.querySelectorAll('button');
                const selectButtons = Array.from(allButtons).filter(btn =>
                    btn.textContent.trim().replace(/\\s/g, '') === '选择'
                );

                for (const btn of selectButtons) {
                    // Go up to find a container that has the target merchant ID
                    let container = btn.parentElement;
                    for (let i = 0; i < 10 && container; i++) {
                        const text = container.textContent || '';
                        if (text.includes(targetStoreId)) {
                            // Found the right store card, click the button
                            btn.click();
                            return { success: true, clicked: 'select_button', storeId: targetStoreId };
                        }
                        container = container.parentElement;
                    }
                }

                return { success: false, reason: 'store_not_found' };
            }''', store_id)

            if isinstance(clicked, dict) and clicked.get('success'):
                logger.info(f"Clicked '选 择' button, waiting for page to load...")

                # Wait for navigation to complete
                await asyncio.sleep(3)

                # Verify we left the selectorg page
                if not self.is_on_selectorg_page():
                    logger.info(f"Successfully entered store: {store_name or store_id}")
                    logger.info(f"Current URL: {self.page.url}")
                    return True
                else:
                    # Maybe page is still loading, wait more
                    await asyncio.sleep(3)
                    if not self.is_on_selectorg_page():
                        logger.info(f"Successfully entered store: {store_name or store_id}")
                        return True
                    else:
                        logger.error("Still on selectorg page after clicking")
                        return False
            else:
                reason = clicked.get('reason', 'unknown') if isinstance(clicked, dict) else 'unknown'
                logger.error(f"Failed to select store. Reason: {reason}")
                return False

        except Exception as e:
            logger.error(f"Error selecting store: {e}", exc_info=True)
            return False

    async def get_current_store(self) -> Optional[Dict[str, str]]:
        """
        Get the currently selected store information from the header.

        The header shows: "StoreName 商户号: XXXXXXXX"

        Returns:
            Dictionary with 'store_id' and 'store_name', or None if not found
        """
        try:
            # If on selectorg page, no store is selected yet
            if self.is_on_selectorg_page():
                return None

            current_store = await self.page.evaluate('''() => {
                // Look for merchant ID pattern in header area
                const header = document.querySelector('header, [class*="header"], nav, .ant-layout-header');
                if (!header) return null;

                const headerText = header.textContent;

                // Find merchant ID (8-digit number)
                const idMatch = headerText.match(/商户号[：:\\s]*(\\d{8})/);
                if (!idMatch) return null;

                const storeId = idMatch[1];

                // Find store name (contains 店） or 火锅）)
                let storeName = '';
                const allElements = header.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent?.trim() || '';
                    if ((text.endsWith('店）') || text.endsWith('火锅）')) &&
                        text.includes('（') &&
                        text.length < 30 &&
                        el.children.length === 0) {
                        storeName = text;
                        break;
                    }
                }

                return { store_id: storeId, store_name: storeName };
            }''')

            if current_store:
                logger.debug(f"Current store: {current_store['store_name']} (ID: {current_store['store_id']})")

            return current_store

        except Exception as e:
            logger.error(f"Error getting current store: {e}")
            return None

    # Keep old methods for backward compatibility but mark as deprecated
    async def get_all_stores(self) -> List[Dict[str, str]]:
        """
        Get all available stores. Uses selectorg page method.

        Returns:
            List of store dictionaries
        """
        return await self.get_all_stores_from_selectorg()

    async def switch_to_store(self, store_id: str, store_name: str = "") -> bool:
        """
        Switch to a specific store. Uses selectorg page method.

        Args:
            store_id: The merchant/store ID
            store_name: The store name (optional)

        Returns:
            bool: True if successful
        """
        return await self.select_store(store_id, store_name)
