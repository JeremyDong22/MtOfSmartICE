"""
Verified DOM Selectors for Meituan Merchant Backend

These selectors were verified using Chrome DevTools MCP on 2025-12-14.
Report: 储值支付方式明细表 (Stored Value Payment Method Details)
"""

# Navigation selectors (top navigation bar)
NAVIGATION = {
    "operations_center": 'link:has-text("运营中心")',
    "marketing_center": 'link:has-text("营销中心")',
    "inventory": 'link:has-text("库存管理")',
    "reports": 'link:has-text("报表中心")',
    "service_market": 'link:has-text("服务市场")',
}

# Sidebar menu selectors
SIDEBAR = {
    "home": 'menuitem:has-text("首页")',
    "channels": 'button:has-text("渠道")',
    "users": 'button:has-text("用户")',
    "promotions": 'button:has-text("大促活动")',
    "reviews": 'button:has-text("评价管理")',
    "data_reports": 'button:has-text("数据报表")',
}

# Report filter selectors (inside iframe)
REPORT_FILTERS = {
    # Statistics dimension radio buttons
    "dimension_date": 'radio:has-text("日期")',
    "dimension_store": 'radio:has-text("店铺")',
    "dimension_all": 'radio:has-text("全选")',

    # Date range inputs
    "start_date": 'textbox[placeholder*="开始日期"], textbox:near(:text("自然日"))',
    "end_date": 'textbox[placeholder*="结束日期"]',

    # Card type selectors
    "card_category": 'combobox:near(:text("卡种类"))',
    "card_type": 'combobox:near(:text("卡类型"))',

    # Deposit radio buttons
    "include_deposit_yes": 'radio:has-text("是"):near(:text("是否包含押金"))',
    "include_deposit_no": 'radio:has-text("否"):near(:text("是否包含押金"))',

    # Action buttons
    "query_button": 'button:has-text("查询")',
    "reset_button": 'button:has-text("重置")',
    "collapse_filters": 'button:has-text("收起筛选")',
    "export_button": 'button:has-text("导出")',
}

# Main data table selectors
DATA_TABLE = {
    # Column headers
    "header_date": 'columnheader:has-text("日期")',
    "header_store": 'text="店铺"',
    "header_principal": 'columnheader:has-text("本金")',
    "header_bonus": 'columnheader:has-text("赠金")',
    "header_total": 'columnheader:has-text("合计")',

    # Row data (relative selectors)
    "data_rows": 'tr',  # Inside the iframe table
    "view_details_button": 'button:has-text("查看订单明细")',

    # Pagination
    "total_records": 'text=/共 \\d+ 条记录/',
    "prev_page": 'button:has-text("left")',
    "next_page": 'button:has-text("right")',
    "page_size": 'combobox:near(:text("条/页"))',
}

# Order details dialog selectors
ORDER_DETAILS_DIALOG = {
    "dialog": 'dialog:has-text("订单明细")',
    "close_button": 'button:has-text("Close")',

    # Detail table headers
    "header_order_id": 'columnheader:has-text("订单编号")',
    "header_order_time": 'columnheader:has-text("订单时间")',
    "header_order_status": 'columnheader:has-text("订单状态")',
    "header_order_source": 'columnheader:has-text("订单来源")',
    "header_principal": 'columnheader:has-text("本金")',
    "header_bonus": 'columnheader:has-text("赠金")',
    "header_deposit": 'columnheader:has-text("押金")',
    "header_phone": 'columnheader:has-text("手机号")',
    "header_card_number": 'columnheader:has-text("会员卡号")',

    # Pagination in dialog
    "dialog_total_records": 'dialog >> text=/共 \\d+ 条记录/',
}

# Store selection page selectors
STORE_SELECTION = {
    "page_title": 'text="请选择要登录的集团/门店"',
    "search_input": 'input[placeholder="请输入机构名称/编码"]',
    "search_button": 'button:has(img[alt="search"])',
    "city_filter": 'combobox[aria-autocomplete="list"]',
    "select_button": 'button:has-text("选 择")',
}

# Common popup/dialog selectors
POPUPS = {
    "tutorial_got_it": 'button:has-text("我知道了")',
    "tutorial_skip": 'button:has-text("跳过")',
    "tutorial_next": 'button:has-text("下一步")',
    "close_button": 'button:has-text("关闭")',
    "cancel_button": 'button:has-text("取消")',
    "confirm_button": 'button:has-text("确定")',
}

# URLs
URLS = {
    "login": "https://eepassport.meituan.com/portal/login",
    "store_selection": "https://pos.meituan.com/web/rms-account#/selectorg",
    "operations_center": "https://pos.meituan.com/web/operation/main#/",
    "marketing_center": "https://pos.meituan.com/web/marketing/home#/rms-discount/marketing",
    "inventory": "https://pos.meituan.com/web/web-scm/scm-home",
    "reports": "https://pos.meituan.com/web/report/main#/rms-report/home",
    "service_market": "https://pos.meituan.com/web/service-market/home#/rms-online/service-market/home",

    # Direct report URL (requires store to be selected first)
    "stored_value_payment_report": "https://pos.meituan.com/web/marketing/crm/report/dpaas-summary-payment",
}

# Store configuration
STORES = [
    {"name": "宁桂杏山野烤肉（绵阳1958店）", "merchant_id": "56756952", "org_code": "MD00006"},
    {"name": "宁桂杏山野烤肉（常熟世贸店）", "merchant_id": "56728236", "org_code": "MD00007"},
    {"name": "野百灵·贵州酸汤火锅（1958店）", "merchant_id": "56799302", "org_code": "MD00008"},
    {"name": "宁桂杏山野烤肉（上马店）", "merchant_id": "58188193", "org_code": "MD00009"},
    {"name": "野百灵·贵州酸汤火锅（德阳店）", "merchant_id": "58121229", "org_code": "MD00010"},
    {"name": "宁桂杏山野烤肉（江油首店）", "merchant_id": "58325928", "org_code": "MD00011"},
]

# Report data structure (verified from live page)
REPORT_COLUMNS = {
    "summary_table": [
        "序号",           # Row number
        "日期",           # Date
        "店铺",           # Store name
        "法人",           # Legal entity
        "分公司",         # Branch
        "市场",           # Market
        "机构编码",       # Organization code
        "交易机构ID",     # Transaction org ID
        "本金",           # Principal (净储值金额_充值)
        "赠金",           # Bonus
        "合计",           # Total
        "扫码支付-微信",  # WeChat payment
        "扫码支付-支付宝", # Alipay payment
        "合计",           # Payment total
        "操作",           # Actions (查看订单明细)
    ],
    "detail_table": [
        "序号",           # Row number
        "订单编号",       # Order ID
        "订单时间",       # Order time
        "订单状态",       # Order status
        "订单来源",       # Order source
        "本金",           # Principal amount
        "赠金",           # Bonus amount
        "押金",           # Deposit amount
        "手机号",         # Phone number (masked)
        "会员卡号",       # Membership card number
    ],
}
