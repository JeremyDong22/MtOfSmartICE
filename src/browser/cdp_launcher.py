"""
CDP Launcher - Chrome DevTools Protocol browser initialization
v1.0

This module handles Chrome browser initialization with CDP support:
- Detects if Chrome is already running with CDP on the specified port
- Launches a new Chrome instance with CDP if needed
- Uses a separate profile directory to avoid conflicts with existing Chrome sessions
"""

import asyncio
import subprocess
import platform
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple

from src.config import CDP_URL

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CDP_PORT = 9222
DEFAULT_PROFILE_DIR = "/Users/jeremydong/Desktop/Smartice/APPs/MtOfSmartICE/data/chrome-profile"
DEFAULT_STARTUP_URL = "https://pos.meituan.com"
CDP_CHECK_TIMEOUT = 2.0
CDP_STARTUP_TIMEOUT = 20.0  # Allow more time for initial page load


def get_chrome_path() -> str:
    """
    Get the Chrome executable path based on the operating system.

    Returns:
        str: Path to Chrome executable

    Raises:
        RuntimeError: If Chrome is not found
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Linux":
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    else:
        raise RuntimeError(f"Unsupported operating system: {system}")

    for path in paths:
        if Path(path).exists():
            return path

    raise RuntimeError(f"Chrome not found. Checked paths: {paths}")


async def check_cdp_available(port: int = DEFAULT_CDP_PORT) -> bool:
    """
    Check if Chrome CDP is available on the specified port.

    Args:
        port: CDP port number

    Returns:
        bool: True if CDP is available, False otherwise
    """
    url = f"http://localhost:{port}/json/version"

    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=CDP_CHECK_TIMEOUT) as response:
            if response.status == 200:
                import json
                data = json.loads(response.read().decode())
                logger.info(f"CDP available on port {port}: {data.get('Browser', 'Unknown')}")
                return True
    except Exception as e:
        logger.debug(f"CDP not available on port {port}: {e}")

    return False


async def launch_chrome_with_cdp(
    port: int = DEFAULT_CDP_PORT,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    startup_url: str = DEFAULT_STARTUP_URL
) -> bool:
    """
    Launch Chrome with CDP enabled.

    Args:
        port: CDP port number
        profile_dir: Chrome profile directory (separate from default to avoid conflicts)
        startup_url: Initial URL to load

    Returns:
        bool: True if Chrome was launched successfully

    Raises:
        RuntimeError: If Chrome cannot be launched
    """
    chrome_path = get_chrome_path()

    # Create profile directory if needed
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    # Chrome launch arguments
    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        startup_url
    ]

    logger.info(f"Launching Chrome with CDP on port {port}...")
    logger.debug(f"Chrome command: {' '.join(args)}")

    try:
        # Launch Chrome as a detached subprocess
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Wait for CDP to become available (check every 0.3s)
        max_attempts = 20
        for attempt in range(max_attempts):
            await asyncio.sleep(0.3)
            if await check_cdp_available(port):
                logger.info(f"Chrome CDP ready on port {port}")
                return True

        logger.error(f"Chrome started but CDP not responding after {CDP_STARTUP_TIMEOUT}s")
        return False

    except Exception as e:
        logger.error(f"Failed to launch Chrome: {e}")
        raise RuntimeError(f"Failed to launch Chrome: {e}")


async def ensure_cdp_available(
    port: int = DEFAULT_CDP_PORT,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    startup_url: str = DEFAULT_STARTUP_URL
) -> Tuple[bool, bool]:
    """
    Ensure Chrome CDP is available, launching Chrome if necessary.

    This is the main entry point for CDP initialization. It will:
    1. Check if CDP is already running on the port
    2. If yes, reuse the existing connection
    3. If no, launch a new Chrome instance with CDP

    Args:
        port: CDP port number
        profile_dir: Chrome profile directory
        startup_url: Initial URL to load if launching new Chrome

    Returns:
        Tuple[bool, bool]: (success, was_launched)
            - success: True if CDP is available
            - was_launched: True if we launched a new Chrome instance
    """
    # Check if CDP is already available
    if await check_cdp_available(port):
        logger.info(f"Reusing existing Chrome CDP on port {port}")
        return (True, False)

    # Launch new Chrome instance
    logger.info(f"Chrome CDP not found on port {port}, launching new instance...")
    success = await launch_chrome_with_cdp(port, profile_dir, startup_url)

    return (success, True)


def get_cdp_url(port: int = DEFAULT_CDP_PORT) -> str:
    """
    Get the CDP URL for the specified port.

    Args:
        port: CDP port number

    Returns:
        str: CDP URL (e.g., "http://localhost:9222")
    """
    return f"http://localhost:{port}"


# Synchronous wrapper for command-line usage
def ensure_cdp_available_sync(
    port: int = DEFAULT_CDP_PORT,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    startup_url: str = DEFAULT_STARTUP_URL
) -> Tuple[bool, bool]:
    """
    Synchronous wrapper for ensure_cdp_available.

    For use in synchronous contexts or command-line scripts.
    """
    return asyncio.run(ensure_cdp_available(port, profile_dir, startup_url))


if __name__ == "__main__":
    # Test the CDP launcher
    logging.basicConfig(level=logging.INFO)

    async def test():
        success, was_launched = await ensure_cdp_available()
        if success:
            if was_launched:
                print("Launched new Chrome instance with CDP")
            else:
                print("Reusing existing Chrome CDP")
            print(f"CDP URL: {get_cdp_url()}")
        else:
            print("Failed to ensure CDP availability")

    asyncio.run(test())
