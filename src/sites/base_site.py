# Base Site - Abstract base class for all website locators
# v1.0 - Initial creation
#
# Provides common functionality for:
# - Login detection
# - Navigation to specific pages
# - Iframe handling
# - Popup dismissal

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class BaseSite(ABC):
    """
    Abstract base class for website locators.

    Each site implementation handles:
    1. Login detection and prompt
    2. Account/organization selection
    3. Navigation to specific report pages
    4. Iframe detection and handling
    """

    # Subclasses should override these
    SITE_NAME: str = "BaseSite"
    BASE_URL: str = ""
    LOGIN_URL: str = ""

    def __init__(self, page: Page):
        """
        Initialize site with a Playwright page.

        Args:
            page: Playwright page object (already connected via CDP)
        """
        self.page = page
        self.frame = None  # Will be set after navigation if iframe is used

    @abstractmethod
    async def is_logged_in(self) -> bool:
        """
        Check if user is logged in to this site.

        Returns:
            bool: True if logged in, False otherwise
        """
        pass

    @abstractmethod
    async def navigate_to_report(self, report_name: str) -> bool:
        """
        Navigate to a specific report page.

        Args:
            report_name: Name/identifier of the report to navigate to

        Returns:
            bool: True if navigation successful
        """
        pass

    @abstractmethod
    async def get_available_reports(self) -> list:
        """
        Get list of available reports/crawlers for this site.

        Returns:
            List of report identifiers
        """
        pass

    async def dismiss_popups(self) -> None:
        """
        Dismiss any tutorial or promotional popups.
        Common across most sites.
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
                button = await self.page.query_selector(
                    f'button:has-text("{text}")',
                    timeout=2000
                )
                if button:
                    await button.click()
                    logger.info(f"Dismissed popup: {text}")
                    await asyncio.sleep(0.5)
            except:
                pass

        # Try clicking backdrop
        try:
            backdrop = await self.page.query_selector(
                '[class*="mask"], [class*="backdrop"]',
                timeout=2000
            )
            if backdrop:
                await backdrop.click()
                await asyncio.sleep(0.5)
        except:
            pass

    async def get_iframe(self, iframe_pattern: str) -> Any:
        """
        Get iframe by URL pattern.

        Args:
            iframe_pattern: Pattern to match in iframe URL

        Returns:
            Frame object or main page if not found
        """
        main_url = self.page.url
        for frame in self.page.frames:
            if frame.url == main_url:
                continue
            if iframe_pattern in frame.url:
                logger.info(f"Found iframe: {frame.url}")
                return frame

        logger.warning(f"Iframe '{iframe_pattern}' not found, using main page")
        return self.page

    async def wait_for_navigation(self, timeout: int = 60000) -> bool:
        """
        Wait for page navigation to complete.

        Args:
            timeout: Timeout in milliseconds

        Returns:
            bool: True if navigation completed
        """
        try:
            await self.page.wait_for_load_state('networkidle', timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Navigation timeout: {e}")
            return False

    def __repr__(self) -> str:
        return f"{self.SITE_NAME}(url={self.page.url})"
