# Meituan Guanjia Site - Website locator for pos.meituan.com
# v1.2 - Optimized navigation wait strategy
#   - Changed wait_until from 'networkidle' to 'domcontentloaded'
#   - Prevents timeout during peak hours when network activity doesn't stabilize
#
# Handles:
# - Login detection
# - 集团账号 (group account) selection
# - Navigation to various report pages within 美团管家

import asyncio
import logging
from typing import Optional, Dict, Any, List
from playwright.async_api import Page

from src.sites.base_site import BaseSite

logger = logging.getLogger(__name__)


# URLs for 美团管家
SELECTORG_URL = "https://pos.meituan.com/web/rms-account#/selectorg"
MARKETING_CENTER_URL = "https://pos.meituan.com/web/marketing/home#/rms-discount/marketing"

# Available reports in 美团管家
REPORTS = {
    "equity_package_sales": {
        "name": "权益包售卖汇总表",
        "url": "https://pos.meituan.com/web/marketing/crm/report/right-package",
        "iframe_pattern": "crm-smart",
        "path": ["营销中心", "数据报表", "权益包售卖汇总表"]
    },
    "business_summary": {
        "name": "综合营业统计",
        "url": "https://pos.meituan.com/web/report/businessSummary#/rms-report/businessSummary",
        "iframe_pattern": "dpaas-report",
        "path": ["报表中心", "营业报表", "综合营业统计"]
    },
    "dish_sales": {
        "name": "菜品综合统计",
        "url": "https://pos.meituan.com/web/report/dishSaleAnalysis#/rms-report/dishSaleAnalysis",
        "iframe_pattern": None,  # Data is on main page, not in iframe
        "path": ["报表中心", "菜品报表", "菜品综合统计"]
    },
}


class MeituanGuanjiaSite(BaseSite):
    """
    Website locator for 美团管家 (pos.meituan.com).

    Handles navigation through the 美团管家 backend system:
    1. Login detection
    2. 集团账号 selection (for aggregated multi-store data)
    3. Navigation to specific report pages
    4. iframe detection (crm-smart)
    """

    SITE_NAME = "美团管家"
    BASE_URL = "https://pos.meituan.com"
    LOGIN_URL = "https://eepassport.meituan.com/portal/login"

    def __init__(self, page: Page):
        super().__init__(page)
        self.group_selected = False

    async def is_logged_in(self) -> bool:
        """
        Check if user is logged in to 美团管家.

        Returns:
            bool: True if logged in
        """
        current_url = self.page.url

        # If on login page, not logged in
        if "eepassport.meituan.com" in current_url:
            return False

        # If on selectorg page or any pos.meituan.com page, logged in
        if "pos.meituan.com" in current_url:
            return True

        # Try navigating to selectorg to check
        try:
            await self.page.goto(SELECTORG_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(1)

            # If redirected to login, not logged in
            if "eepassport.meituan.com" in self.page.url:
                return False

            return True
        except Exception as e:
            logger.warning(f"Login check failed: {e}")
            return False

    async def select_group_account(self) -> bool:
        """
        Select 集团 (group) account from selectorg page.

        This enables aggregated data view for all stores.

        Returns:
            bool: True if successfully selected
        """
        try:
            # Navigate to selectorg page
            logger.info(f"Navigating to selectorg page: {SELECTORG_URL}")
            await self.page.goto(SELECTORG_URL, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)

            # Find and click the 集团 "选 择" button
            result = await self.page.evaluate('''() => {
                const allButtons = document.querySelectorAll('button');
                const allText = document.body.innerText;

                if (!allText.includes('集团')) {
                    return { success: false, reason: 'no_group_text_found' };
                }

                // Method 1: Find button containing both "集团" and "选 择"
                for (const btn of allButtons) {
                    const text = btn.textContent || '';
                    if (text.includes('集团') && text.includes('选 择')) {
                        const selectBtn = btn.querySelector('button');
                        if (selectBtn && selectBtn.textContent.includes('选 择')) {
                            selectBtn.click();
                            return { success: true, method: 'inner_select_button' };
                        }
                        if (text.trim().endsWith('选 择')) {
                            btn.click();
                            return { success: true, method: 'group_button_direct' };
                        }
                    }
                }

                // Method 2: Find "选 择" buttons and check parent for "集团"
                for (const btn of allButtons) {
                    if (btn.textContent?.trim() === '选 择') {
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
                logger.info(f"Successfully selected 集团 account via {result.get('method')}")
                self.group_selected = True
                await asyncio.sleep(3)  # Wait for account switch
                return True
            else:
                logger.error(f"Failed to select 集团: {result.get('reason')}")
                return False

        except Exception as e:
            logger.error(f"Error selecting group account: {e}")
            await self.capture_debug_screenshot("timeout_select_group")
            return False

    async def navigate_to_report(self, report_name: str) -> bool:
        """
        Navigate to a specific report page.

        Args:
            report_name: Report identifier (key in REPORTS dict)

        Returns:
            bool: True if navigation successful
        """
        if report_name not in REPORTS:
            logger.error(f"Unknown report: {report_name}. Available: {list(REPORTS.keys())}")
            return False

        report = REPORTS[report_name]
        report_url = report["url"]
        iframe_pattern = report.get("iframe_pattern")

        try:
            # Step 1: Select group account if not already done
            if not self.group_selected:
                if not await self.select_group_account():
                    return False

            # Step 2: Navigate to report URL
            logger.info(f"Navigating to {report['name']}: {report_url}")
            await self.page.goto(report_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)

            # Dismiss popups
            await self.dismiss_popups()

            # Verify URL
            current_url = self.page.url
            if report_name == "equity_package_sales" and 'right-package' not in current_url:
                logger.warning(f"Unexpected URL: {current_url}")
                return False

            # Step 3: Get iframe if needed
            if iframe_pattern:
                self.frame = await self.get_iframe(iframe_pattern)
                await asyncio.sleep(1)

                # Check for "切换新版" button (switch to new version)
                await self._switch_to_new_version_if_needed()

            logger.info(f"Successfully navigated to {report['name']}")
            return True

        except Exception as e:
            logger.error(f"Navigation to {report_name} failed: {e}")
            await self.capture_debug_screenshot(f"timeout_navigate_{report_name}")
            return False

    async def _switch_to_new_version_if_needed(self) -> None:
        """
        Check for and click "切换新版" button if present.
        Some reports have old/new version toggle.
        """
        if not self.frame:
            return

        try:
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
                logger.info("Detected old version, clicking '切换新版'...")
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
                await asyncio.sleep(3)
                # Re-acquire iframe
                self.frame = await self.get_iframe('crm-smart')
                logger.info("Switched to new version")

        except Exception as e:
            logger.warning(f"Error checking version switch: {e}")

    async def get_available_reports(self) -> List[Dict[str, str]]:
        """
        Get list of available reports for this site.

        Returns:
            List of report info dicts
        """
        return [
            {
                "id": key,
                "name": value["name"],
                "path": " → ".join(value["path"])
            }
            for key, value in REPORTS.items()
        ]

    def get_frame(self):
        """
        Get the current frame (iframe or main page).

        Returns:
            Frame object for crawler to use
        """
        return self.frame or self.page
