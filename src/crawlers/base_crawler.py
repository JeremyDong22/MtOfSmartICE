"""
Base Crawler - Abstract base class for all crawlers

This provides common functionality and enforces a consistent interface
for all crawler implementations.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page
from datetime import datetime

from src.config import DEFAULT_TIMEOUT, RETRY_DELAY, MAX_RETRIES
from src.utils.date_utils import format_date_for_input, validate_date

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for all crawlers.

    Provides common utilities for:
    - Date handling
    - Error handling and retries
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
    async def crawl(self, store_id: str, store_name: str) -> Dict[str, Any]:
        """
        Execute the crawl for a specific store.

        This method must be implemented by all subclasses.

        Args:
            store_id: The merchant/store ID
            store_name: The store name

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

    async def set_date_filter(self, start_date: str, end_date: str) -> bool:
        """
        Set date range filter in the report using calendar clicks.

        The Ant Design date picker requires clicking on calendar day cells,
        not filling text into inputs.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse dates
            start_parts = start_date.split('-')
            end_parts = end_date.split('-')
            start_day = int(start_parts[2])
            end_day = int(end_parts[2])
            start_year = int(start_parts[0])
            start_month = int(start_parts[1])

            logger.info(f"Setting date range: {start_date} to {end_date} (days: {start_day}, {end_day})")

            # Step 1: Click on start date input to open calendar
            start_input = await self.frame.query_selector('input[placeholder="开始日期"]')
            if not start_input:
                logger.error("Start date input not found")
                return False

            await start_input.click()
            await asyncio.sleep(1)

            # Step 2: Navigate to correct month/year if needed
            await self._navigate_calendar_to_month(start_year, start_month)

            # Step 3: Click on start day in calendar
            start_clicked = await self._click_calendar_day(start_day, 'left')
            if not start_clicked:
                logger.error(f"Could not click start day {start_day}")
                await self.page.keyboard.press('Escape')
                return False

            await asyncio.sleep(0.5)

            # Step 4: Click on end day in calendar
            # The end date input should now be focused and calendar still open
            end_clicked = await self._click_calendar_day(end_day, 'left')
            if not end_clicked:
                logger.error(f"Could not click end day {end_day}")
                await self.page.keyboard.press('Escape')
                return False

            await asyncio.sleep(0.5)

            # Close calendar if still open
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.3)

            # Verify dates were set
            verify = await self.frame.evaluate('''() => {
                const startInput = document.querySelector('input[placeholder="开始日期"]');
                const endInput = document.querySelector('input[placeholder="结束日期"]');
                return {
                    start: startInput ? startInput.value : null,
                    end: endInput ? endInput.value : null
                };
            }''')

            logger.info(f"Date verification: start={verify['start']}, end={verify['end']}")
            return True

        except Exception as e:
            logger.error(f"Error setting date filter: {e}")
            return False

    async def _navigate_calendar_to_month(self, year: int, month: int) -> bool:
        """
        Navigate calendar to the specified month/year if needed.

        Args:
            year: Target year
            month: Target month (1-12)

        Returns:
            bool: True if successful
        """
        try:
            # Check current calendar month and navigate if needed
            for _ in range(24):  # Max 2 years of navigation
                current = await self.frame.evaluate('''() => {
                    const picker = document.querySelector('.ant-picker-dropdown, .saas-picker-dropdown');
                    if (!picker) return null;
                    const yearBtn = picker.querySelector('button[class*="year"]');
                    const monthBtn = picker.querySelector('button[class*="month"]');
                    return {
                        year: yearBtn ? parseInt(yearBtn.textContent) : null,
                        month: monthBtn ? parseInt(monthBtn.textContent) : null
                    };
                }''')

                if not current or current.get('year') is None:
                    # Calendar might use different structure, try simpler approach
                    return True

                cal_year = current.get('year')
                cal_month = current.get('month')

                if cal_year == year and cal_month == month:
                    return True

                # Need to navigate
                if cal_year > year or (cal_year == year and cal_month > month):
                    # Go back (previous month)
                    await self.frame.evaluate('''() => {
                        const picker = document.querySelector('.ant-picker-dropdown, .saas-picker-dropdown');
                        if (picker) {
                            const prevBtn = picker.querySelector('button[class*="prev-icon"], .ant-picker-header-prev-btn');
                            if (prevBtn) prevBtn.click();
                        }
                    }''')
                else:
                    # Go forward (next month)
                    await self.frame.evaluate('''() => {
                        const picker = document.querySelector('.ant-picker-dropdown, .saas-picker-dropdown');
                        if (picker) {
                            const nextBtn = picker.querySelector('button[class*="next-icon"], .ant-picker-header-next-btn');
                            if (nextBtn) nextBtn.click();
                        }
                    }''')

                await asyncio.sleep(0.3)

            return True
        except Exception as e:
            logger.warning(f"Error navigating calendar: {e}")
            return True  # Continue anyway

    async def _click_calendar_day(self, day: int, panel: str = 'left') -> bool:
        """
        Click on a specific day in the calendar picker.

        Args:
            day: Day number (1-31)
            panel: Which panel to click ('left' or 'right')

        Returns:
            bool: True if click successful
        """
        try:
            # Use JavaScript to find and click the correct day cell
            clicked = await self.frame.evaluate(f'''(targetDay) => {{
                // Find calendar picker dropdown
                const picker = document.querySelector('.ant-picker-dropdown, .saas-picker-dropdown');
                if (!picker) return false;

                // Find all panels (usually left = current month, right = next month)
                const panels = picker.querySelectorAll('.ant-picker-panel, .saas-picker-panel');
                const panelIndex = '{panel}' === 'left' ? 0 : 1;
                const targetPanel = panels[panelIndex] || panels[0];

                if (!targetPanel) return false;

                // Find all day cells in the target panel
                const dayCells = targetPanel.querySelectorAll(
                    '.ant-picker-cell-inner, .saas-picker-cell-inner, td[class*="cell"]:not([class*="disabled"])'
                );

                for (const cell of dayCells) {{
                    const cellText = cell.textContent.trim();
                    // Match exact day number
                    if (cellText === String(targetDay)) {{
                        // Check this is not a day from prev/next month (usually has different class)
                        const parentCell = cell.closest('td');
                        if (parentCell && !parentCell.classList.contains('ant-picker-cell-disabled')) {{
                            cell.click();
                            return true;
                        }}
                    }}
                }}

                // Fallback: try clicking any element with the exact day text
                const allElements = picker.querySelectorAll('td');
                for (const td of allElements) {{
                    const inner = td.querySelector('.ant-picker-cell-inner, .saas-picker-cell-inner');
                    if (inner && inner.textContent.trim() === String(targetDay)) {{
                        const isDisabled = td.classList.contains('ant-picker-cell-disabled') ||
                                          td.classList.contains('ant-picker-cell-in-view') === false;
                        if (!isDisabled || td.classList.contains('ant-picker-cell-in-view')) {{
                            inner.click();
                            return true;
                        }}
                    }}
                }}

                return false;
            }}''', day)

            if clicked:
                logger.info(f"Clicked day {day} in {panel} panel")
                return True
            else:
                logger.warning(f"Could not find day {day} in calendar")
                return False

        except Exception as e:
            logger.error(f"Error clicking calendar day: {e}")
            return False

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

    async def wait_for_element(
        self,
        selector: str,
        timeout: int = DEFAULT_TIMEOUT,
        state: str = 'visible'
    ) -> bool:
        """
        Wait for an element to appear.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
            state: Element state to wait for

        Returns:
            bool: True if element found, False otherwise
        """
        try:
            await self.frame.wait_for_selector(selector, timeout=timeout, state=state)
            logger.debug(f"Element found: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Element not found: {selector} - {e}")
            return False

    async def click_with_retry(
        self,
        selector: str,
        max_retries: int = MAX_RETRIES,
        delay: int = RETRY_DELAY
    ) -> bool:
        """
        Click an element with retry logic.

        Args:
            selector: CSS selector
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                element = await self.frame.query_selector(selector)
                if element:
                    await element.click()
                    logger.debug(f"Clicked: {selector}")
                    return True
                else:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries}: Element not found: {selector}")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Click failed: {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(delay)

        return False

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

    async def safe_evaluate(self, script: str, default_value: Any = None) -> Any:
        """
        Safely execute JavaScript with error handling.

        Args:
            script: JavaScript code to execute
            default_value: Value to return on error

        Returns:
            Result of script execution or default_value on error
        """
        try:
            result = await self.frame.evaluate(script)
            return result
        except Exception as e:
            logger.warning(f"JavaScript evaluation failed: {e}")
            return default_value
