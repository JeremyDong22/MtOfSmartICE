"""
CDP Session Manager - Simplified browser connection using CDP only
v1.1 - Added find_page_by_url() to locate correct page by URL pattern

This module provides a simple wrapper around Playwright's CDP connection
for connecting to an existing Chrome instance.
"""

import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from src.config import CDP_URL, DEFAULT_TIMEOUT, NAVIGATION_TIMEOUT

logger = logging.getLogger(__name__)


class CDPSession:
    """
    Manages connection to existing Chrome browser via CDP (Chrome DevTools Protocol).

    This is a simplified browser manager that only connects to existing Chrome instances
    and does not launch new browsers.
    """

    def __init__(self, cdp_url: str = CDP_URL):
        """
        Initialize CDP session manager.

        Args:
            cdp_url: CDP endpoint URL (default: http://localhost:9222)
        """
        self.cdp_url = cdp_url
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def connect(self) -> BrowserContext:
        """
        Connect to existing Chrome browser via CDP.

        Returns:
            BrowserContext: The browser context

        Raises:
            RuntimeError: If connection fails
        """
        try:
            logger.info(f"Connecting to Chrome via CDP: {self.cdp_url}")

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)

            # Get existing context or create new one
            if self.browser.contexts:
                self.context = self.browser.contexts[0]
                logger.info(f"Using existing browser context with {len(self.context.pages)} pages")
            else:
                self.context = await self.browser.new_context()
                logger.info("Created new browser context")

            return self.context

        except Exception as e:
            logger.error(f"Failed to connect to Chrome via CDP: {e}")
            raise RuntimeError(f"CDP connection failed: {e}")

    async def get_page(self, url_pattern: str = None) -> Page:
        """
        Get a page, optionally matching a URL pattern.

        Args:
            url_pattern: Optional URL substring to match. If provided, finds the
                        first page whose URL contains this pattern.

        Returns:
            Page: The browser page

        Raises:
            RuntimeError: If context not connected
        """
        if not self.context:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.context.pages:
            # If URL pattern provided, find matching page
            if url_pattern:
                for page in self.context.pages:
                    if url_pattern in page.url:
                        logger.info(f"Found page matching '{url_pattern}': {page.url}")
                        return page
                # If no match found, log available pages and return first
                logger.warning(f"No page matching '{url_pattern}'. Available pages:")
                for i, p in enumerate(self.context.pages):
                    logger.warning(f"  [{i}] {p.url}")

            page = self.context.pages[0]
            logger.debug(f"Using existing page: {page.url}")
            return page

        page = await self.context.new_page()
        logger.info("Created new page")
        return page

    async def navigate(self, page: Page, url: str, wait_until: str = 'networkidle') -> bool:
        """
        Navigate to a URL with error handling.

        Args:
            page: The page to navigate
            url: URL to navigate to
            wait_until: When to consider navigation succeeded

        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            logger.info(f"Navigating to: {url}")
            await page.goto(url, wait_until=wait_until, timeout=NAVIGATION_TIMEOUT)
            await asyncio.sleep(1)  # Brief pause for stability
            logger.info(f"Successfully navigated to: {page.url}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    async def wait_for_selector(
        self,
        page: Page,
        selector: str,
        timeout: int = DEFAULT_TIMEOUT,
        state: str = 'visible'
    ) -> bool:
        """
        Wait for a selector to be present.

        Args:
            page: The page to wait on
            selector: CSS selector to wait for
            timeout: Timeout in milliseconds
            state: State to wait for ('visible', 'attached', 'hidden')

        Returns:
            bool: True if selector found, False otherwise
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout, state=state)
            logger.debug(f"Selector found: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Selector not found: {selector} - {e}")
            return False

    async def close(self) -> None:
        """
        Close the CDP connection and cleanup resources.

        Note: This does NOT close the Chrome browser itself, only disconnects.
        """
        try:
            if self.context:
                # Don't close context when using CDP - just disconnect
                self.context = None
                logger.info("Disconnected from browser context")

            if self.browser:
                # Close browser connection (not the browser itself)
                await self.browser.close()
                self.browser = None
                logger.info("Closed browser connection")

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                logger.info("Stopped Playwright")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def dismiss_popups(self, page: Page) -> None:
        """
        Attempt to dismiss common popups and tutorial dialogs.

        Args:
            page: The page to dismiss popups on
        """
        dismiss_texts = [
            "我知道了",
            "跳过",
            "关闭",
            "取消",
            "知道了",
            "×"
        ]

        for text in dismiss_texts:
            try:
                button = await page.query_selector(f'button:has-text("{text}")', timeout=2000)
                if button:
                    await button.click()
                    logger.info(f"Dismissed popup with button: {text}")
                    await asyncio.sleep(0.5)
            except:
                pass

        # Try clicking backdrop
        try:
            backdrop = await page.query_selector('[class*="mask"], [class*="backdrop"]', timeout=2000)
            if backdrop:
                await backdrop.click()
                await asyncio.sleep(0.5)
        except:
            pass

    def __repr__(self) -> str:
        """String representation of CDP session."""
        connected = "connected" if self.context else "disconnected"
        return f"CDPSession(url={self.cdp_url}, status={connected})"


async def test_cdp_connection():
    """Test CDP connection - for development/debugging."""
    session = CDPSession()

    try:
        await session.connect()
        page = await session.get_page()

        print(f"Connected successfully!")
        print(f"Current URL: {page.url}")
        print(f"Page title: {await page.title()}")

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_cdp_connection())
