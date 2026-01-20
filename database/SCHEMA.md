# Database Schema
<!-- v1.3 - 2025-01-20 - Added mt_dish_sales table for dish-level sales statistics -->

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

### mt_dish_sales
菜品综合统计数据表（来自报表中心→营业报表→菜品综合统计）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| store_name | TEXT | 门店名称 |
| org_code | TEXT | 机构编码 |
| business_date | TEXT | 营业日期 (YYYY-MM-DD) |
| dish_name | TEXT | 菜品名称 |
| sales_quantity | INTEGER | 销售数量 |
| sales_quantity_pct | REAL | 销售数量占比 |
| price_before_discount | REAL | 折前均价 |
| price_after_discount | REAL | 折后均价 |
| sales_amount | REAL | 销售额 |
| sales_amount_pct | REAL | 销售额占比 |
| discount_amount | REAL | 优惠金额 |
| dish_discount_pct | REAL | 菜品优惠占比 |
| dish_income | REAL | 菜品收入 |
| dish_income_pct | REAL | 菜品收入占比 |
| order_quantity | INTEGER | 点菜数量 |
| order_amount | REAL | 点菜金额 |
| return_quantity | INTEGER | 退菜数量 |
| return_amount | REAL | 退菜金额 |
| return_quantity_pct | REAL | 退菜数量占比 |
| return_amount_pct | REAL | 退菜金额占比 |
| return_rate | REAL | 退菜率 |
| return_order_count | INTEGER | 退菜订单量 |
| gift_quantity | INTEGER | 赠菜数量 |
| gift_amount | REAL | 赠菜金额 |
| gift_quantity_pct | REAL | 赠菜数量占比 |
| gift_amount_pct | REAL | 赠菜金额占比 |
| dish_order_count | INTEGER | 菜品销售订单量 |
| related_order_amount | REAL | 关联订单金额 |
| sales_per_thousand | REAL | 菜品销售千次 |
| order_rate | REAL | 菜品点单率 |
| customer_click_rate | REAL | 顾客点击率 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**唯一约束**: `(store_name, business_date, dish_name)`

**索引**:
- `idx_dish_sales_store_date`: (store_name, business_date)
- `idx_dish_sales_date`: (business_date)
- `idx_dish_sales_dish_name`: (dish_name)

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

### mt_dish_sales
菜品综合统计数据表（云端版本，使用中文列名）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| restaurant_id | UUID | 外键 → master_restaurant.id |
| 营业日期 | DATE | 营业日期 |
| 菜品名称 | TEXT | 菜品名称 |
| 销售数量 | INTEGER | 销售数量 |
| 销售数量占比 | NUMERIC | 销售数量占比 |
| 折前均价 | NUMERIC | 折前均价 |
| 折后均价 | NUMERIC | 折后均价 |
| 销售额 | NUMERIC | 销售额 |
| 销售额占比 | NUMERIC | 销售额占比 |
| 优惠金额 | NUMERIC | 优惠金额 |
| 菜品优惠占比 | NUMERIC | 菜品优惠占比 |
| 菜品收入 | NUMERIC | 菜品收入 |
| 菜品收入占比 | NUMERIC | 菜品收入占比 |
| 点菜数量 | INTEGER | 点菜数量 |
| 点菜金额 | NUMERIC | 点菜金额 |
| 退菜数量 | INTEGER | 退菜数量 |
| 退菜金额 | NUMERIC | 退菜金额 |
| 退菜数量占比 | NUMERIC | 退菜数量占比 |
| 退菜金额占比 | NUMERIC | 退菜金额占比 |
| 退菜率 | NUMERIC | 退菜率 |
| 退菜订单量 | INTEGER | 退菜订单量 |
| 赠菜数量 | INTEGER | 赠菜数量 |
| 赠菜金额 | NUMERIC | 赠菜金额 |
| 赠菜数量占比 | NUMERIC | 赠菜数量占比 |
| 赠菜金额占比 | NUMERIC | 赠菜金额占比 |
| 菜品销售订单量 | INTEGER | 菜品销售订单量 |
| 关联订单金额 | NUMERIC | 关联订单金额 |
| 菜品销售千次 | NUMERIC | 菜品销售千次 |
| 菜品点单率 | NUMERIC | 菜品点单率 |
| 顾客点击率 | NUMERIC | 顾客点击率 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**唯一约束**: `(restaurant_id, 营业日期, 菜品名称)`

**索引**:
- `idx_dish_sales_restaurant_date`: (restaurant_id, 营业日期)
- `idx_dish_sales_date`: (营业日期)
- `idx_dish_sales_dish_name`: (菜品名称)

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
