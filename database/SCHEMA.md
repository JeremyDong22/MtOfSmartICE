# Database Schema
<!-- v1.2 - 2025-12-18 - Changed Supabase mt_business_summary column names to Chinese -->

本文档描述美团爬虫项目的数据库结构，包括本地 SQLite 和云端 Supabase。

## 本地 SQLite (`database/meituan_data.db`)

### mt_stores
门店基础信息表。

| 字段 | 类型 | 说明 |
|------|------|------|
| org_code | TEXT | 主键，美团机构编码 (如 MD00007) |
| store_name | TEXT | 门店名称 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### mt_equity_package_sales
权益包销售数据表。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| org_code | TEXT | 外键 → mt_stores.org_code |
| date | TEXT | 销售日期 (YYYY-MM-DD) |
| package_name | TEXT | 套餐名称 (如 "山海会员") |
| unit_price | REAL | 单价 |
| quantity_sold | INTEGER | 售卖数量 |
| total_sales | REAL | 售卖总额 |
| refund_quantity | INTEGER | 退款数量 |
| refund_amount | REAL | 退款金额 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**唯一约束**: `(org_code, date, package_name)`

**索引**:
- `idx_equity_sales_org_date`: (org_code, date)
- `idx_equity_sales_date`: (date)

### mt_business_summary
综合营业统计数据表（来自报表中心→营业报表→综合营业统计）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| store_name | TEXT | 门店名称 |
| business_date | TEXT | 营业日期 (YYYY-MM-DD) |
| city | TEXT | 城市 |
| store_created_at | TEXT | 门店创建时间 |
| operating_days | INTEGER | 营业天数 |
| revenue | REAL | 营业额 |
| discount_amount | REAL | 折扣金额 |
| business_income | REAL | 营业收入 |
| order_count | INTEGER | 订单数 |
| diner_count | INTEGER | 就餐人数 |
| table_count | INTEGER | 开台数 |
| per_capita_before_discount | REAL | 折前人均 |
| per_capita_after_discount | REAL | 折后人均 |
| avg_order_before_discount | REAL | 折前单均 |
| avg_order_after_discount | REAL | 折后单均 |
| table_opening_rate | TEXT | 开台率 |
| table_turnover_rate | REAL | 翻台率 |
| occupancy_rate | TEXT | 上座率 |
| avg_dining_time | INTEGER | 平均用餐时长(分钟) |
| composition_data | TEXT | 渠道/收入/支付构成(JSON) |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**唯一约束**: `(store_name, business_date)`

---

## 云端 Supabase

### master_restaurant
门店主数据表（全局共享）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| restaurant_name | TEXT | 门店名称 |
| meituan_org_code | TEXT | 美团机构编码（用于映射） |
| ... | ... | 其他字段省略 |

### mt_equity_package_sales
权益包销售数据表（云端版本）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| restaurant_id | UUID | 外键 → master_restaurant.id |
| date | DATE | 销售日期 |
| package_name | TEXT | 套餐名称 |
| unit_price | NUMERIC | 单价 |
| quantity_sold | INTEGER | 售卖数量 |
| total_sales | NUMERIC | 售卖总额 |
| refund_quantity | INTEGER | 退款数量 |
| refund_amount | NUMERIC | 退款金额 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**唯一约束**: `(restaurant_id, date, package_name)`

### mt_business_summary
综合营业统计数据表（云端版本，使用中文列名）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| restaurant_id | UUID | 外键 → master_restaurant.id |
| 营业日期 | DATE | 营业日期 |
| 城市 | TEXT | 城市 |
| 门店创建时间 | TEXT | 门店创建时间 |
| 营业天数 | INTEGER | 营业天数 |
| 营业额 | NUMERIC | 营业额 |
| 折扣金额 | NUMERIC | 折扣金额 |
| 营业收入 | NUMERIC | 营业收入 |
| 订单数 | INTEGER | 订单数 |
| 就餐人数 | INTEGER | 就餐人数 |
| 开台数 | INTEGER | 开台数 |
| 折前人均 | NUMERIC | 折前人均 |
| 折后人均 | NUMERIC | 折后人均 |
| 折前单均 | NUMERIC | 折前单均 |
| 折后单均 | NUMERIC | 折后单均 |
| 开台率 | TEXT | 开台率 |
| 翻台率 | NUMERIC | 翻台率 |
| 上座率 | TEXT | 上座率 |
| 平均用餐时长 | INTEGER | 平均用餐时长(分钟) |
| 构成数据 | JSONB | 渠道/收入/支付构成 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**唯一约束**: `(restaurant_id, 营业日期)`

**索引**:
- `idx_business_summary_restaurant_date`: (restaurant_id, 营业日期)
- `idx_business_summary_date`: (营业日期)

---

## 门店映射表

本地 org_code 与 Supabase restaurant_id 的映射关系。

| org_code | restaurant_name | restaurant_id | 状态 |
|----------|-----------------|---------------|------|
| MD00006 | 宁桂杏1958店 | c732129d-1513-4425-9485-e2461c8c9429 | 已映射 |
| MD00007 | 宁桂杏世贸店 | 9a43fb67-7c4c-4c8f-b1dd-5e22911ecdbf | 已映射 |
| MD00008 | 野百灵1958店 | 7dda9c35-be62-47fb-b9ce-daddec67c47f | 已映射 |
| MD00009 | 宁桂杏上马店 | 96592966-31b7-4ca5-b6bd-109318b57cf5 | 已映射 |
| MD00010 | 野百灵同森店 | e1b8f10f-c548-40de-bb6b-4174c0575393 | 已映射 |
| MD00011 | 宁桂杏江油店 | a89d7071-659c-41f7-b2df-be42c635b05b | 已映射 |
| MD00012 | 野百灵上马店 | 5ad5e15b-95d5-432c-a414-143b44caf1f6 | 已映射 |

### 未映射门店（Supabase 中有但无 org_code）
| restaurant_name | restaurant_id |
|-----------------|---------------|
| 宁桂杏四丈湾店 | 0f9b4767-b43e-47cb-b1d2-46c3cde1a55d |
| 野百灵世贸店 | 0b9e9031-4223-4124-b633-e3a853abfb8f |

---

## 维护说明

1. **新增门店映射**: 在 Supabase `master_restaurant` 表中更新 `meituan_org_code` 字段
2. **爬虫遇到未知门店**: 会在日志中提示，需手动添加映射
3. **更新此文档**: 每次修改门店映射后，同步更新本文档的映射表
