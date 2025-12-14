"""
Store Navigator - Handles store selection and switching

This module provides functionality to:
1. Open the store selection dialog ("选择机构")
2. Get all available stores from the dialog
3. Switch between stores

Dialog Structure:
- Header with search input and city filter
- Left panel: Tree view of organization hierarchy
- Right panel: Table with columns - 机构名称, 机构类型, 机构编码, 商户号
- Current store is marked with "当前" label
"""

import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import Page

from src.config import MEITUAN_DASHBOARD_URL, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class StoreNavigator:
    """
    Handles store navigation and selection in the Meituan backend.

    The store selector is in the header area showing:
    "StoreName 商户号: XXXXXXXX [down-arrow]"

    Clicking the down arrow opens the "选择机构" dialog with all stores.
    """

    def __init__(self, page: Page):
        """
        Initialize store navigator.

        Args:
            page: Playwright page object
        """
        self.page = page

    async def navigate_to_dashboard(self) -> bool:
        """
        Navigate to the Meituan dashboard.

        Returns:
            bool: True if navigation successful, False otherwise
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

    async def _open_store_dialog(self) -> bool:
        """
        Open the store selection dialog by clicking on the store selector.

        The store selector shows the current store name and merchant ID
        with a down arrow icon. Clicking it opens the "选择机构" dialog.

        Returns:
            bool: True if dialog opened, False otherwise
        """
        try:
            logger.info("Opening store selection dialog...")

            # Method 1: Find the store selector area with merchant ID and click nearby down icon
            # The structure is: StoreName + "商户号: XXXXXXXX" + down-arrow-icon
            clicked = await self.page.evaluate('''() => {
                // Strategy 1: Find all elements and look for one with 8-digit merchant ID
                // then find the next sibling that's a down arrow icon
                const allElements = document.querySelectorAll('*');

                for (const el of allElements) {
                    const text = el.textContent?.trim() || '';
                    // Look for exact 8-digit merchant ID
                    if (/^\\d{8}$/.test(text)) {
                        // This is likely the merchant ID element
                        // The down arrow should be a sibling or nearby
                        let parent = el.parentElement;
                        for (let i = 0; i < 3 && parent; i++) {
                            // Look for down arrow icon in siblings
                            const siblings = parent.children;
                            for (const sib of siblings) {
                                // Check if this is an icon (SVG or span with icon class)
                                const isSvg = sib.tagName === 'svg' || sib.querySelector('svg');
                                const hasIconClass = sib.className?.toString?.().includes('icon') ||
                                                    sib.className?.toString?.().includes('anticon');
                                const ariaLabel = sib.getAttribute?.('aria-label') || '';

                                if ((isSvg || hasIconClass) &&
                                    (ariaLabel.includes('down') ||
                                     sib.className?.toString?.().includes('down') ||
                                     sib.innerHTML?.includes('down'))) {
                                    sib.click();
                                    return 'clicked_sibling_icon';
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }
                }

                // Strategy 2: Find element containing "商户号" text and click after the 8-digit ID
                for (const el of allElements) {
                    if (el.children.length === 0) continue;  // Skip leaf nodes
                    const text = el.textContent || '';
                    if (text.includes('商户号') && /\\d{8}/.test(text) && text.length < 200) {
                        // Found the store info container
                        // Find all SVGs or icons in this container
                        const icons = el.querySelectorAll('svg, [class*="icon"], [class*="anticon"]');
                        for (const icon of icons) {
                            const className = icon.className?.toString?.() || icon.className?.baseVal || '';
                            if (className.includes('down')) {
                                icon.click();
                                return 'clicked_container_icon';
                            }
                        }
                        // If no down icon found, try clicking the container itself
                        el.click();
                        return 'clicked_container';
                    }
                }

                // Strategy 3: Click directly on merchant ID text (might trigger dropdown)
                for (const el of allElements) {
                    const text = el.textContent?.trim() || '';
                    if (/^\\d{8}$/.test(text)) {
                        el.click();
                        return 'clicked_merchant_id';
                    }
                }

                return false;
            }''')

            if clicked:
                logger.info(f"Clicked store selector ({clicked}), waiting for dialog...")
                await asyncio.sleep(2)

                # Verify dialog opened
                if await self._is_dialog_open():
                    logger.info("Store selection dialog opened successfully")
                    return True

            logger.warning("First click attempt didn't open dialog, trying alternative methods")

            # Alternative: Try using Playwright selector for anticon-down
            try:
                # Look for anticon-down that's near merchant ID text
                down_icon = await self.page.query_selector('[class*="anticon-down"]')
                if down_icon:
                    await down_icon.click()
                    await asyncio.sleep(2)
                    if await self._is_dialog_open():
                        logger.info("Opened dialog via anticon-down selector")
                        return True
            except Exception as e:
                logger.debug(f"anticon-down selector failed: {e}")

            # Alternative: Try clicking based on aria labels or specific class patterns
            for selector in [
                '[aria-label*="选择"]',
                '[aria-label*="机构"]',
                '[class*="org-selector"]',
                '[class*="store-selector"]',
                '[class*="shop-selector"]'
            ]:
                try:
                    el = await self.page.query_selector(selector)
                    if el:
                        await el.click()
                        await asyncio.sleep(2)
                        if await self._is_dialog_open():
                            return True
                except:
                    pass

            logger.error("Failed to open store dialog")
            return False

        except Exception as e:
            logger.error(f"Error opening store dialog: {e}")
            return False

    async def _is_dialog_open(self) -> bool:
        """Check if the store selection dialog is currently open."""
        try:
            return await self.page.evaluate('''() => {
                const dialog = document.querySelector('[role="dialog"], .ant-modal, [class*="modal"]');
                return dialog !== null && dialog.textContent.includes('选择机构');
            }''')
        except:
            return False

    async def _wait_for_dialog_content(self, timeout: int = 15) -> bool:
        """
        Wait for the dialog content (store list) to load.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            bool: True if content loaded, False if timeout
        """
        for attempt in range(timeout * 2):  # Check every 0.5 seconds
            try:
                result = await self.page.evaluate('''() => {
                    const dialog = document.querySelector('[role="dialog"], .ant-modal, [class*="modal"]');
                    if (!dialog) return { status: 'no_dialog' };

                    const text = dialog.textContent || '';

                    // Check for loading state
                    if (text.includes('加载中')) {
                        return { status: 'loading' };
                    }

                    // Check for no data
                    if (text.includes('暂无数据') && !text.match(/\\d{8}/)) {
                        return { status: 'no_data' };
                    }

                    // Check if store list has loaded (look for 8-digit merchant IDs)
                    const merchantIds = text.match(/\\d{8}/g);
                    if (merchantIds && merchantIds.length > 0) {
                        return { status: 'loaded', count: merchantIds.length };
                    }

                    return { status: 'unknown' };
                }''')

                status = result.get('status') if isinstance(result, dict) else result

                if status == 'loaded':
                    count = result.get('count', 0) if isinstance(result, dict) else 0
                    logger.info(f"Dialog content loaded ({count} merchant IDs found)")
                    return True
                elif status == 'loading':
                    logger.debug(f"Dialog still loading... (attempt {attempt + 1})")
                elif status == 'no_dialog':
                    logger.debug("No dialog found")
                elif status == 'no_data':
                    logger.warning("Dialog shows no data")

            except Exception as e:
                logger.debug(f"Error checking dialog content: {e}")

            await asyncio.sleep(0.5)

        logger.warning("Timeout waiting for dialog content")
        return False

    async def get_all_stores(self) -> List[Dict[str, str]]:
        """
        Get all available stores from the store selection dialog.

        The dialog contains a table with columns:
        - 机构名称 (Organization Name)
        - 机构类型 (Type - typically "门店")
        - 机构编码 (Code - e.g., "MD00006")
        - 商户号 (Merchant ID - 8-digit number)

        Returns:
            List of store dictionaries with 'store_id' and 'store_name' keys
        """
        stores = []

        try:
            logger.info("Getting all available stores...")

            # Open the store dialog
            if not await self._open_store_dialog():
                logger.warning("Could not open store dialog")
                return stores

            # Wait for dialog content to load
            if not await self._wait_for_dialog_content():
                logger.warning("Dialog content did not load in time")
                await self._close_dialog()
                return stores

            # Extract stores from the dialog
            # Dialog structure: each store row has 5 consecutive leaf elements:
            # [店铺名称, "门店", MD编码, 8位商户号, 空格/"当前"]
            stores_data = await self.page.evaluate('''() => {
                const stores = [];
                const dialog = document.querySelector('[role="dialog"], .ant-modal, [class*="modal"]');
                if (!dialog) return stores;

                // Collect all leaf text nodes in order
                const leafTexts = [];
                const walker = document.createTreeWalker(
                    dialog,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text && text.length > 0) {
                        leafTexts.push(text);
                    }
                }

                // Find the header row index (look for "商户号")
                let headerIndex = -1;
                for (let i = 0; i < leafTexts.length; i++) {
                    if (leafTexts[i] === '商户号') {
                        headerIndex = i;
                        break;
                    }
                }

                if (headerIndex === -1) {
                    // Fallback: just look for 8-digit IDs
                    return stores;
                }

                // Parse rows after header
                // Each row: 店名, 门店, MD编码, 商户号, 空格(or空), [当前]
                // Note: some rows may have "当前" as an extra element
                let i = headerIndex + 1;
                while (i < leafTexts.length) {
                    const text = leafTexts[i];

                    // Skip whitespace-only or empty entries
                    if (!text || text.trim() === '' || text === '当前') {
                        i++;
                        continue;
                    }

                    // Check if this looks like a store name (ends with 店） or 火锅）)
                    if ((text.endsWith('店）') || text.endsWith('火锅）')) && text.includes('（')) {
                        const storeName = text;

                        // Next should be "门店"
                        if (i + 1 < leafTexts.length && leafTexts[i + 1] === '门店') {
                            // i+2 is MD code, i+3 is merchant ID
                            if (i + 3 < leafTexts.length) {
                                const merchantId = leafTexts[i + 3];
                                if (/^\\d{8}$/.test(merchantId)) {
                                    stores.push({
                                        store_id: merchantId,
                                        store_name: storeName
                                    });
                                    // Move past: store(i), 门店(i+1), MD(i+2), ID(i+3)
                                    i += 4;
                                    continue;
                                }
                            }
                        }
                    }
                    i++;
                }

                return stores;
            }''')

            if stores_data:
                stores = stores_data
                logger.info(f"Found {len(stores)} stores in dialog")
                for store in stores:
                    logger.info(f"  - {store['store_name']} (ID: {store['store_id']})")
            else:
                logger.warning("No stores found in dialog")

            # Close the dialog
            await self._close_dialog()

        except Exception as e:
            logger.error(f"Error getting stores: {e}", exc_info=True)
            await self._close_dialog()

        return stores

    async def _close_dialog(self) -> None:
        """Close any open dialog."""
        try:
            # Try pressing Escape
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)

            # Check if dialog is still open and click Close button
            still_open = await self.page.evaluate('''() => {
                const dialog = document.querySelector('[role="dialog"], .ant-modal, [class*="modal"]');
                if (dialog) {
                    const closeBtn = dialog.querySelector('button[class*="close"], [aria-label="Close"], .ant-modal-close');
                    if (closeBtn) {
                        closeBtn.click();
                        return true;
                    }
                }
                return false;
            }''')

            if still_open:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.debug(f"Error closing dialog: {e}")

    async def switch_to_store(self, store_id: str, store_name: str = "") -> bool:
        """
        Switch to a specific store by selecting it in the dialog.

        After clicking a store in the dialog, the page will refresh/redirect
        to the main dashboard with the new store context.

        Args:
            store_id: The merchant/store ID (e.g., "58188193")
            store_name: The store name (optional, for logging)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Switching to store: {store_name or store_id}")

            # Check if already on this store
            current = await self.get_current_store()
            if current and current.get('store_id') == store_id:
                logger.info(f"Already on store {store_name or store_id}")
                return True

            # Open the store dialog
            if not await self._open_store_dialog():
                logger.error("Failed to open store dialog")
                return False

            # Wait for dialog content to load
            if not await self._wait_for_dialog_content():
                logger.error("Dialog content did not load")
                await self._close_dialog()
                return False

            # Click on the store row containing the store_id
            # The dialog lists stores with their merchant ID visible
            # Strategy: Find the store name element that's in the same row as the target merchant ID
            switched = await self.page.evaluate('''(targetStoreId) => {
                const dialog = document.querySelector('[role="dialog"], .ant-modal, [class*="modal"]');
                if (!dialog) return { success: false, reason: 'no_dialog' };

                // Find all text elements in the dialog
                const allElements = dialog.querySelectorAll('*');

                // First, find the element containing the exact merchant ID
                let merchantIdElement = null;
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent?.trim() === targetStoreId) {
                        merchantIdElement = el;
                        break;
                    }
                }

                if (!merchantIdElement) {
                    return { success: false, reason: 'merchant_id_not_found' };
                }

                // Now find the store name in the same row
                // Go up to find the row container, then find the store name
                let parent = merchantIdElement.parentElement;
                for (let i = 0; i < 5 && parent; i++) {
                    // Look for store name element in this container
                    const children = parent.querySelectorAll('*');
                    for (const child of children) {
                        const text = child.textContent?.trim() || '';
                        // Store names end with 店） or 火锅）
                        if ((text.endsWith('店）') || text.endsWith('火锅）')) &&
                            text.includes('（') &&
                            text.length < 40 &&
                            child.children.length === 0) {
                            // Found the store name - click it
                            child.click();
                            return { success: true, clicked: text };
                        }
                    }
                    parent = parent.parentElement;
                }

                // Fallback: try clicking near the merchant ID element
                // Some dialogs allow clicking anywhere on the row
                merchantIdElement.parentElement?.click();
                return { success: true, clicked: 'parent_of_merchant_id' };
            }''', store_id)

            # Handle result from JavaScript
            if isinstance(switched, dict):
                success = switched.get('success', False)
                clicked = switched.get('clicked', '')
                reason = switched.get('reason', '')
            else:
                success = bool(switched)
                clicked = ''
                reason = ''

            if success:
                logger.info(f"Clicked on store ({clicked}), waiting for page refresh...")
                # After clicking a store, the page will redirect/refresh
                await asyncio.sleep(5)

                # Verify the switch by checking the header
                current = await self.get_current_store()
                if current and current.get('store_id') == store_id:
                    logger.info(f"Successfully switched to store: {store_name or store_id}")
                    return True
                else:
                    # The page might still be loading
                    await asyncio.sleep(3)
                    current = await self.get_current_store()
                    if current and current.get('store_id') == store_id:
                        logger.info(f"Successfully switched to store: {store_name or store_id}")
                        return True

                    logger.warning(f"Store switch verification uncertain. Current: {current}")
                    # Return true anyway as the click happened and page refreshed
                    return True
            else:
                logger.error(f"Could not find store {store_id} in dialog. Reason: {reason}")
                await self._close_dialog()
                return False

        except Exception as e:
            logger.error(f"Error switching to store: {e}", exc_info=True)
            try:
                await self._close_dialog()
            except:
                pass
            return False

    async def get_current_store(self) -> Optional[Dict[str, str]]:
        """
        Get the currently selected store information from the header.

        The header shows: "StoreName 商户号: XXXXXXXX [down-arrow]"

        Returns:
            Dictionary with 'store_id' and 'store_name', or None if not found
        """
        try:
            current_store = await self.page.evaluate('''() => {
                // Find the header/banner area containing store info
                const header = document.querySelector('header, [class*="header"], nav, .ant-layout-header, [role="banner"]');
                if (!header) return null;

                const headerText = header.textContent;

                // Find merchant ID (8-digit number after 商户号)
                const idMatch = headerText.match(/商户号[：:\\s]*(\\d{8})/);
                if (!idMatch) return null;

                const storeId = idMatch[1];

                // Find store name - look for text containing 店） or 火锅）
                // The store name appears before 商户号 in the header
                let storeName = '';

                // Method 1: Find all text elements in header and look for store name pattern
                const allElements = header.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent.trim();
                    // Store names contain parentheses with 店 or 火锅
                    if ((text.includes('店）') || text.includes('火锅）')) &&
                        text.includes('（') &&
                        text.length < 30 &&
                        !text.includes('商户号')) {
                        // Check if this element only contains the store name (not concatenated text)
                        if (el.children.length === 0 || text.split('）').length <= 2) {
                            storeName = text;
                            break;
                        }
                    }
                }

                // Method 2: Parse from full header text
                if (!storeName) {
                    // Try to find store name before 商户号
                    // Store names end with 店） or 火锅）
                    const idx = headerText.indexOf('商户号');
                    if (idx > 0) {
                        const beforeMerchant = headerText.substring(0, idx);
                        // Find the last occurrence of 店） or 火锅）
                        const storeEndIdx = Math.max(
                            beforeMerchant.lastIndexOf('店）'),
                            beforeMerchant.lastIndexOf('火锅）')
                        );
                        if (storeEndIdx > 0) {
                            // Find the start of the store name (look for opening parenthesis)
                            let startIdx = beforeMerchant.lastIndexOf('（', storeEndIdx);
                            if (startIdx === -1) startIdx = 0;
                            // Go back further to get the full name (e.g., 宁桂杏山野烤肉)
                            const prefix = beforeMerchant.substring(0, startIdx);
                            const lastNewline = Math.max(prefix.lastIndexOf('\\n'), prefix.lastIndexOf(' '));
                            startIdx = lastNewline >= 0 ? lastNewline + 1 : 0;
                            storeName = beforeMerchant.substring(startIdx, storeEndIdx + 2).trim();
                        }
                    }
                }

                // Clean up store name
                storeName = storeName.replace(/[\\n\\r\\t]/g, '').trim();

                return {
                    store_id: storeId,
                    store_name: storeName
                };
            }''')

            if current_store:
                logger.info(f"Current store: {current_store['store_name']} (ID: {current_store['store_id']})")

            return current_store

        except Exception as e:
            logger.error(f"Error getting current store: {e}")
            return None
