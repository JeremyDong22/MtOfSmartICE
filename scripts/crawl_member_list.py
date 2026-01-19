#!/usr/bin/env python3
"""
Member List Crawler - Extracts all customer data from 美团管家 会员列表
Crawls ~3,800 pages of member data including full phone numbers
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

CDP_URL = "http://localhost:9222"
MEMBER_LIST_URL = "https://pos.meituan.com/web/marketing/member/basic/member-list#/"
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


async def connect_to_browser(cdp_url: str):
    """Connect to Chrome via CDP"""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else await context.new_page()
    return playwright, browser, page


async def navigate_to_member_list(page):
    """Navigate to member list page"""
    print("Navigating to member list...")

    # Check if already on member list page
    if "member-list" in page.url:
        print("Already on member list page")
        return True

    # Navigate to group account selection if needed
    if "selectorg" not in page.url and "pos.meituan.com/web" not in page.url:
        print("Navigating to group account selection...")
        await page.goto("https://pos.meituan.com/web/rms-account#/selectorg", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Select group account
        print("Selecting group account...")
        await page.evaluate('''() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent || '';
                if (text.includes('集团') && text.includes('选') && text.includes('择')) {
                    btn.click();
                    return true;
                }
            }
        }''')
        await asyncio.sleep(3)

    # Navigate to member list
    print("Navigating to member list page...")
    await page.goto(MEMBER_LIST_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    return True


async def get_iframe(page):
    """Find and return the member list iframe"""
    # The iframe has the same URL as main page, so we need to find it by checking if it's actually an iframe
    for frame in page.frames:
        if frame != page.main_frame and "member/basic/member-list" in frame.url:
            return frame
    # If no iframe found, return main frame (might be the content is in main page)
    return page.main_frame


async def reveal_phone_numbers(frame):
    """Click all eye icons to reveal full phone numbers"""
    result = await frame.evaluate('''() => {
        const icons = document.querySelectorAll('.icon-visibility-off');
        let count = 0;
        for (const icon of icons) {
            icon.click();
            count++;
        }
        return { clicked: count };
    }''')

    if result['clicked'] > 0:
        await asyncio.sleep(1.5)  # Wait for numbers to update

    return result['clicked']


async def extract_page_data(frame):
    """Extract all member data from current page"""
    data = await frame.evaluate('''() => {
        const rows = [];
        const tbody = document.querySelector('tbody');
        if (!tbody) return rows;

        const trs = tbody.querySelectorAll('tr');
        for (const tr of trs) {
            const cells = tr.querySelectorAll('td');
            if (cells.length < 15) continue;

            // Skip checkbox column (index 0)
            rows.push({
                name: cells[1]?.textContent?.trim() || '',
                phone: cells[2]?.textContent?.trim() || '',
                card_count: cells[3]?.textContent?.trim() || '',
                store: cells[4]?.textContent?.trim() || '',
                source: cells[5]?.textContent?.trim() || '',
                platform: cells[6]?.textContent?.trim() || '',
                scenario: cells[7]?.textContent?.trim() || '',
                tags: cells[8]?.textContent?.trim() || '',
                balance: cells[9]?.textContent?.trim() || '',
                points: cells[10]?.textContent?.trim() || '',
                consumption_count: cells[11]?.textContent?.trim() || '',
                total_consumption: cells[12]?.textContent?.trim() || '',
                last_consumption_time: cells[13]?.textContent?.trim() || '',
                join_time: cells[14]?.textContent?.trim() || '',
                first_recharge_time: cells[15]?.textContent?.trim() || ''
            });
        }
        return rows;
    }''')

    return data


async def get_pagination_info(frame):
    """Get total pages and current page"""
    info = await frame.evaluate('''() => {
        const totalMatch = document.body.innerText.match(/共\\s*(\\d+)\\s*条/);
        const totalRecords = totalMatch ? parseInt(totalMatch[1]) : 0;

        // Try to find page input
        let pageInput = document.querySelector('input[type="number"]');
        let currentPage = 1;
        let totalPages = 1;

        if (pageInput) {
            currentPage = parseInt(pageInput.value || '1');
            totalPages = parseInt(pageInput.max || '1');
        } else {
            // Calculate from total records if input not found
            // Default is 10 records per page
            const perPageMatch = document.body.innerText.match(/(\\d+)条\\/页/);
            const perPage = perPageMatch ? parseInt(perPageMatch[1]) : 10;
            totalPages = Math.ceil(totalRecords / perPage);
        }

        return { total_records: totalRecords, current_page: currentPage, total_pages: totalPages };
    }''')

    return info


async def go_to_page(frame, target_page: int):
    """Navigate to specific page"""
    result = await frame.evaluate('''(targetPage) => {
        // Try clicking page number
        const pageItems = document.querySelectorAll('.el-pager li');
        for (const el of pageItems) {
            if (el.textContent?.trim() === String(targetPage)) {
                el.click();
                return { success: true, method: 'click' };
            }
        }

        // Use input field
        const pageInput = document.querySelector('input[type="number"]');
        if (pageInput) {
            pageInput.value = targetPage;
            pageInput.dispatchEvent(new Event('input', { bubbles: true }));
            pageInput.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'Enter', keyCode: 13, bubbles: true
            }));
            return { success: true, method: 'input' };
        }

        return { success: false };
    }''', target_page)

    await asyncio.sleep(2)  # Wait for page to load
    return result['success']


def save_to_csv(data, filepath, mode='a'):
    """Save data to CSV file"""
    if not data:
        return

    fieldnames = [
        'name', 'phone', 'card_count', 'store', 'source', 'platform',
        'scenario', 'tags', 'balance', 'points', 'consumption_count',
        'total_consumption', 'last_consumption_time', 'join_time',
        'first_recharge_time'
    ]

    file_exists = filepath.exists()
    with open(filepath, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists or mode == 'w':
            writer.writeheader()
        writer.writerows(data)


async def crawl_all_pages(frame, output_file, max_pages=None):
    """Crawl all pages and save data"""
    # Get pagination info
    info = await get_pagination_info(frame)
    total_pages = info['total_pages']
    total_records = info['total_records']

    # Limit pages if max_pages specified
    if max_pages:
        total_pages = min(total_pages, max_pages)
        print(f"\n[TEST MODE] Limiting to {max_pages} pages")

    print(f"\nTotal records: {total_records:,}")
    print(f"Total pages: {total_pages:,}")
    print(f"Output file: {output_file}\n")

    all_data = []
    start_time = datetime.now()

    for page_num in range(1, total_pages + 1):
        try:
            # Navigate to page if not on page 1
            if page_num > 1:
                success = await go_to_page(frame, page_num)
                if not success:
                    print(f"Failed to navigate to page {page_num}, retrying...")
                    await asyncio.sleep(2)
                    await go_to_page(frame, page_num)

            # Reveal phone numbers
            clicked = await reveal_phone_numbers(frame)

            # Extract data
            page_data = await extract_page_data(frame)
            all_data.extend(page_data)

            # Progress update
            if page_num % 50 == 0 or page_num == 1:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = page_num / elapsed if elapsed > 0 else 0
                remaining = (total_pages - page_num) / rate if rate > 0 else 0
                print(f"Page {page_num}/{total_pages} ({page_num/total_pages*100:.1f}%) | "
                      f"Records: {len(all_data):,} | "
                      f"Rate: {rate:.1f} pages/sec | "
                      f"ETA: {remaining/60:.0f}m")

            # Save incrementally every 100 pages
            if page_num % 100 == 0:
                save_to_csv(all_data, output_file, mode='w' if page_num == 100 else 'a')
                print(f"  → Saved {len(all_data):,} records to disk")
                all_data = []  # Clear memory

        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            await asyncio.sleep(3)
            continue

    # Save remaining data
    if all_data:
        save_to_csv(all_data, output_file, mode='a')
        print(f"  → Saved final {len(all_data):,} records")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n✓ Crawl complete!")
    print(f"  Total time: {elapsed/60:.1f} minutes")
    print(f"  Output: {output_file}")


async def main():
    """Main entry point"""
    print("=" * 60)
    print("Member List Crawler")
    print("=" * 60)

    # Check for test mode
    max_pages = None
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        max_pages = 5
        print("[TEST MODE] Will crawl only 5 pages")

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = DATA_DIR / f"member_list_{timestamp}.csv"

    playwright = None
    try:
        # Connect to browser
        print("Connecting to Chrome CDP...")
        playwright, browser, page = await connect_to_browser(CDP_URL)
        print(f"✓ Connected to {page.url}")

        # Navigate to member list
        await navigate_to_member_list(page)

        # Get iframe
        print("Finding member list iframe...")
        frame = await get_iframe(page)
        if not frame:
            print("✗ Could not find member list iframe")
            return
        print(f"✓ Found iframe: {frame.url}")

        # Crawl all pages
        await crawl_all_pages(frame, output_file, max_pages=max_pages)

    except KeyboardInterrupt:
        print("\n\n✗ Crawl interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if playwright:
            await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
