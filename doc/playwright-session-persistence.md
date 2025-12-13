# Playwright Browser Session Persistence - Technical Documentation

## Overview

This document describes how to maintain browser login sessions across script executions using Playwright's persistent context feature. This technique eliminates the need for repeated manual logins when automating authenticated web applications.

---

## Core Mechanism: `launch_persistent_context()`

### What It Does

Unlike standard `browser.launch()` which creates ephemeral browser instances, `launch_persistent_context()` creates a browser with a **persistent user data directory** that stores all browser state to disk.

```python
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir='./user_data/session_1',
            headless=False,
            channel='chrome'
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto('https://example.com')
        # Session cookies, localStorage, etc. are automatically preserved
        await context.close()
```

### Key Difference from Regular Launch

| Aspect | `browser.launch()` | `launch_persistent_context()` |
|--------|-------------------|------------------------------|
| State persistence | None (incognito-like) | Full disk persistence |
| Cookies | Lost on close | Saved to disk |
| localStorage | Lost on close | Saved to disk |
| IndexedDB | Lost on close | Saved to disk |
| Browser cache | None | Cached to disk |
| Login sessions | Must re-login | Preserved across restarts |

---

## What Gets Stored

### User Data Directory Structure

```
user_data/session_1/
├── Default/                    # Chrome default profile
│   ├── Cookies                 # SQLite database - all cookies
│   ├── Local Storage/          # Origin-keyed localStorage data
│   │   └── leveldb/            # LevelDB files
│   ├── IndexedDB/              # IndexedDB databases per origin
│   ├── Session Storage/        # Session storage (limited persistence)
│   ├── Cache/                  # HTTP cache
│   ├── Code Cache/             # V8 compiled JavaScript cache
│   ├── GPUCache/               # GPU shader cache
│   ├── History                 # Browsing history (SQLite)
│   ├── Preferences             # Browser preferences (JSON)
│   ├── Secure Preferences      # Encrypted preferences
│   └── Web Data                # Autofill, keywords (SQLite)
├── Local State                 # Browser-level state (JSON)
├── First Run                   # First run marker
└── SingletonLock               # Process lock file
```

### Persistence by Storage Type

| Storage Type | Automatically Persisted | Notes |
|--------------|------------------------|-------|
| Cookies (with Expires) | Yes | Fully persisted |
| Cookies (session) | Partial | May not survive browser restart |
| localStorage | Yes | Origin-scoped |
| IndexedDB | Yes | For Firebase/complex auth |
| sessionStorage | No | Cleared on page unload |
| Cache | Yes | HTTP resources cached |

---

## Implementation Pattern

### Basic Implementation

```python
import asyncio
from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self, user_data_dir: str = './user_data/default'):
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.context = None

    async def start(self, headless: bool = False):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=headless,
            channel='chrome',
            viewport={'width': 1280, 'height': 800},
            args=[
                '--disable-blink-features=AutomationControlled',  # Anti-detection
            ]
        )
        return self.context

    async def get_page(self):
        if self.context.pages:
            return self.context.pages[0]
        return await self.context.new_page()

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

# Usage
async def main():
    manager = BrowserManager('./user_data/meituan_session')
    await manager.start()

    page = await manager.get_page()
    await page.goto('https://example.com/dashboard')

    # First run: User logs in manually
    # Subsequent runs: Already logged in!

    await manager.stop()

asyncio.run(main())
```

### Multi-Account Support

```python
class MultiAccountBrowserManager:
    def __init__(self, base_dir: str = './user_data'):
        self.base_dir = base_dir
        self.playwright = None
        self.contexts: dict[int, BrowserContext] = {}

    async def start(self):
        self.playwright = await async_playwright().start()

    async def get_context(self, account_id: int):
        if account_id in self.contexts:
            return self.contexts[account_id]

        user_data_path = f'{self.base_dir}/account_{account_id}'
        context = await self.playwright.chromium.launch_persistent_context(
            user_data_path,
            headless=False,
            channel='chrome',
            args=['--disable-blink-features=AutomationControlled']
        )
        self.contexts[account_id] = context
        return context

    async def close_context(self, account_id: int):
        if account_id in self.contexts:
            await self.contexts[account_id].close()
            del self.contexts[account_id]

    async def stop(self):
        for context in self.contexts.values():
            await context.close()
        self.contexts.clear()
        if self.playwright:
            await self.playwright.stop()
```

---

## Session Validation

### Check Login Status

```python
async def check_session_valid(page) -> bool:
    """Check if user is still logged in"""

    # Method 1: Check for login-required elements
    login_indicators = await page.evaluate('''() => {
        return {
            hasLoginButton: !!document.querySelector('.login-btn, #login, [href*="login"]'),
            hasUserMenu: !!document.querySelector('.user-menu, .avatar, .profile'),
            hasQRCode: !!document.querySelector('.qrcode, [class*="qr"]'),
        }
    }''')

    if login_indicators['hasQRCode'] or login_indicators['hasLoginButton']:
        return False
    if login_indicators['hasUserMenu']:
        return True

    # Method 2: Check for auth cookies
    cookies = await page.context.cookies()
    auth_cookies = [c for c in cookies if 'token' in c['name'].lower() or 'session' in c['name'].lower()]

    return len(auth_cookies) > 0

async def ensure_logged_in(page, login_url: str):
    """Navigate and verify login, prompt if needed"""
    await page.goto(login_url)

    if not await check_session_valid(page):
        print("Session expired. Please log in manually...")
        # Wait for user to complete login
        await page.wait_for_selector('.user-menu, .avatar', timeout=300000)  # 5 min timeout
        print("Login detected!")
```

---

## Anti-Detection Configuration

### Recommended Browser Arguments

```python
context = await playwright.chromium.launch_persistent_context(
    user_data_dir,
    headless=False,
    channel='chrome',  # Use installed Chrome, not Chromium
    args=[
        '--disable-blink-features=AutomationControlled',  # Hide automation flag
        '--disable-dev-shm-usage',                        # Prevent /dev/shm issues
        '--no-sandbox',                                   # Required in some environments
        '--disable-setuid-sandbox',
        '--disable-accelerated-2d-canvas',
        '--disable-gpu',                                  # Disable GPU (optional)
    ],
    ignore_default_args=['--enable-automation'],          # Remove automation flag
)
```

### Why These Matter

| Argument | Purpose |
|----------|---------|
| `--disable-blink-features=AutomationControlled` | Removes `navigator.webdriver=true` flag |
| `channel='chrome'` | Uses real Chrome instead of Chromium |
| `ignore_default_args=['--enable-automation']` | Removes automation banner |
| `headless=False` | Visible browser is harder to detect |

---

## Handling Common Issues

### Issue: SingletonLock Prevents Launch

When browser crashes, lock file may remain:

```python
import os
import shutil

def cleanup_locks(user_data_dir: str):
    """Remove stale lock files"""
    lock_file = os.path.join(user_data_dir, 'SingletonLock')
    if os.path.exists(lock_file):
        os.remove(lock_file)

    # Also clean up crash files
    for item in ['Crashpad', 'crash_reports']:
        path = os.path.join(user_data_dir, item)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
```

### Issue: Session Cookies Not Persisting

Some cookies marked as "session" cookies (no `Expires`) may not persist:

```python
async def force_persist_cookies(context):
    """Convert session cookies to persistent cookies"""
    cookies = await context.cookies()

    # Set expiry to 1 year from now
    future_expiry = time.time() + (365 * 24 * 60 * 60)

    for cookie in cookies:
        if 'expires' not in cookie or cookie['expires'] == -1:
            cookie['expires'] = future_expiry

    await context.clear_cookies()
    await context.add_cookies(cookies)
```

### Issue: Orphaned Chrome Processes

```python
import subprocess
import os

def kill_orphaned_chrome(user_data_dir: str):
    """Kill Chrome processes using specific user data directory"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'chrome' in line.lower() and user_data_dir in line:
                parts = line.split()
                pid = parts[1]
                os.kill(int(pid), 9)
    except Exception as e:
        print(f"Cleanup error: {e}")
```

---

## Storage State Export/Import

### Alternative to Persistent Context

For cases where you need more control:

```python
# Export state after login
async def save_auth_state(context, path: str):
    """Save cookies and localStorage to file"""
    await context.storage_state(path=path)

# Import state in new context
async def load_auth_state(browser, path: str):
    """Create context with saved auth state"""
    return await browser.new_context(storage_state=path)

# Usage
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # First run - login and save
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto('https://example.com/login')
        # ... perform login ...
        await save_auth_state(context, 'auth_state.json')
        await context.close()

        # Later runs - restore state
        context = await load_auth_state(browser, 'auth_state.json')
        page = await context.new_page()
        await page.goto('https://example.com/dashboard')
        # Already logged in!
```

### When to Use Each Approach

| Approach | Best For |
|----------|----------|
| `launch_persistent_context()` | Long-running crawlers, realistic browser simulation |
| `storage_state()` | Testing, parallel execution, CI/CD |

---

## Best Practices Summary

1. **Use dedicated directories** - Never point to your actual Chrome profile
2. **One directory per account** - Prevents session conflicts
3. **Clean up locks on startup** - Handle previous crashes gracefully
4. **Validate sessions before use** - Check login status, re-auth if needed
5. **Use real Chrome** - Set `channel='chrome'` for better compatibility
6. **Disable automation flags** - Reduces detection risk
7. **Handle graceful shutdown** - Always close context properly to flush state

---

## References

- [Playwright Python - BrowserType.launch_persistent_context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Playwright - Authentication](https://playwright.dev/python/docs/auth)
- [Playwright - BrowserContext.storage_state](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state)
