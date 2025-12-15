"""
Browser management modules
v1.1 - Added CDP launcher for automatic browser initialization
"""

from .cdp_session import CDPSession
from .store_navigator import StoreNavigator
from .cdp_launcher import ensure_cdp_available, check_cdp_available, get_cdp_url

__all__ = ['CDPSession', 'StoreNavigator', 'ensure_cdp_available', 'check_cdp_available', 'get_cdp_url']
