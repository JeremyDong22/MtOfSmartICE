# Sites module - Website locator layer
# v1.0 - Initial creation
#
# This module provides site-specific logic for navigating to different
# Meituan/Dianping websites and handling login, account selection, etc.

from src.sites.base_site import BaseSite
from src.sites.meituan_guanjia import MeituanGuanjiaSite
from src.sites.dianping import DianpingSite

__all__ = ['BaseSite', 'MeituanGuanjiaSite', 'DianpingSite']
