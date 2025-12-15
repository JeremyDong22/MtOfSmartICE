"""
Crawlers module for Meituan backend automation.
v2.0 - Simplified: Removed MembershipCrawler, only EquityPackageSalesCrawler remains

Available crawlers:
- EquityPackageSalesCrawler: Extracts equity package sales data (集团 aggregated)
- BaseCrawler: Abstract base class for all crawlers
"""

from .base_crawler import BaseCrawler
from .权益包售卖汇总表 import EquityPackageSalesCrawler

__all__ = ['BaseCrawler', 'EquityPackageSalesCrawler']
