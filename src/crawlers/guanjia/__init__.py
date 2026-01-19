# Guanjia crawlers - Crawlers for 美团管家 (pos.meituan.com)
# v1.2 - Added DishSalesCrawler for 菜品综合统计

from src.crawlers.guanjia.equity_package_sales import EquityPackageSalesCrawler
from src.crawlers.guanjia.business_summary import BusinessSummaryCrawler
from src.crawlers.guanjia.dish_sales import DishSalesCrawler

__all__ = ['EquityPackageSalesCrawler', 'BusinessSummaryCrawler', 'DishSalesCrawler']
