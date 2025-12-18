# Crawlers module - Data extraction layer
# v3.0 - Restructured by site
#
# Structure:
# - base_crawler.py: Abstract base class for all crawlers
# - guanjia/: Crawlers for 美团管家 (pos.meituan.com)
# - dianping/: Crawlers for 大众点评 (e.dianping.com)
#
# Backward compatibility maintained - old imports still work

from src.crawlers.base_crawler import BaseCrawler

# Backward compatibility - import from new location
from src.crawlers.guanjia import EquityPackageSalesCrawler

# Also keep old import path working
from src.crawlers.guanjia.equity_package_sales import EquityPackageSalesCrawler as 权益包售卖汇总表Crawler

__all__ = ['BaseCrawler', 'EquityPackageSalesCrawler']
