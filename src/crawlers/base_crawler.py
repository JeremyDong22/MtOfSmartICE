"""
Base Crawler - Abstract base class for all crawlers
v2.0 - Simplified: Removed unused methods (calendar date picker, wait_for_element, click_with_retry, safe_evaluate)

This provides common functionality and enforces a consistent interface
for all crawler implementations.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page
from datetime import datetime

from src.utils.date_utils import validate_date

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for all crawlers.

    Provides common utilities for:
    - Date handling
    - Popup dismissal
    - iframe handling
    - Data validation
    """

    def __init__(self, page: Page, frame, db_manager, target_date: str):
        """
        Initialize base crawler.

        Args:
            page: Playwright page object
            frame: The iframe containing the report (or page if no iframe)
            db_manager: Database manager instance
            target_date: Target date in YYYY-MM-DD format
        """
        self.page = page
        self.frame = frame
        self.db = db_manager
        self.target_date = target_date

        # Validate date
        if not validate_date(target_date):
            raise ValueError(f"Invalid date format: {target_date}. Expected YYYY-MM-DD")

    @abstractmethod
    async def crawl(self, store_id: str = None, store_name: str = None) -> Dict[str, Any]:
        """
        Execute the crawl.

        Args:
            store_id: The merchant/store ID (optional for group account crawlers)
            store_name: The store name (optional for group account crawlers)

        Returns:
            Dictionary with crawl results:
            {
                "success": bool,
                "store_id": str,
                "store_name": str,
                "date": str,
                "data": Any,
                "error": Optional[str]
            }
        """
        pass

    async def dismiss_popups(self) -> None:
        """
        Dismiss any tutorial or promotional popups.
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
                button = await self.page.query_selector(f'button:has-text("{text}")', timeout=2000)
                if button:
                    await button.click()
                    logger.info(f"Dismissed popup: {text}")
                    await asyncio.sleep(0.5)
            except:
                pass

        # Try clicking backdrop
        try:
            backdrop = await self.page.query_selector('[class*="mask"], [class*="backdrop"]', timeout=2000)
            if backdrop:
                await backdrop.click()
                await asyncio.sleep(0.5)
        except:
            pass

    def parse_number(self, value: str) -> float:
        """
        Parse number from string, handling Chinese number formatting.

        Args:
            value: String value to parse

        Returns:
            float: Parsed number
        """
        try:
            cleaned = value.replace(',', '').replace('¥', '').replace('元', '').strip()
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0

    def create_result(
        self,
        success: bool,
        store_id: str,
        store_name: str,
        data: Any = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized result dictionary.

        Args:
            success: Whether the crawl succeeded
            store_id: Store ID
            store_name: Store name
            data: Crawled data
            error: Error message if failed

        Returns:
            Dictionary with standardized result format
        """
        return {
            "success": success,
            "store_id": store_id,
            "store_name": store_name,
            "date": self.target_date,
            "data": data,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

    async def get_iframe(self, iframe_name: str = 'crm-smart') -> Any:
        """
        Get iframe by name or URL pattern.

        Args:
            iframe_name: Name or URL pattern to match

        Returns:
            Frame object or main page if not found
        """
        main_url = self.page.url
        for frame in self.page.frames:
            if frame.url == main_url:
                continue
            if iframe_name in frame.url:
                logger.info(f"Found iframe: {frame.url}")
                return frame

        logger.warning(f"Iframe '{iframe_name}' not found, using main page")
        return self.page
