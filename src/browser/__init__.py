"""
Browser management modules
v2.0 - Removed StoreNavigator (unused, current crawler uses 集团 account)
"""

from .cdp_session import CDPSession
from .cdp_launcher import ensure_cdp_available, check_cdp_available, get_cdp_url

__all__ = ['CDPSession', 'ensure_cdp_available', 'check_cdp_available', 'get_cdp_url']
