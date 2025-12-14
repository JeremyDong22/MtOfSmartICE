"""
Crawlers module for Meituan backend automation.

Available crawlers:
- MembershipCrawler: Extracts membership card transaction data
- BaseCrawler: Abstract base class for all crawlers
"""

from .base_crawler import BaseCrawler
from .membership_crawler import MembershipCrawler

__all__ = ['BaseCrawler', 'MembershipCrawler']
