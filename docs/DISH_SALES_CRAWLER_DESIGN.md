# 菜品销售统计爬虫设计文档

## 1. 需求概述

爬取美团管家「报表中心」→「菜品报表」→「菜品销售统计」的数据，记录每个门店每天每道菜的销售数量和金额。

## 2. 页面特点分析

### 2.1 导航路径
- URL: `https://pos.meituan.com/web/report/dish-sale#/rms-report/dishSale`
- 路径: 报表中心 → 菜品报表 → 菜品销售统计

### 2.2 关键差异点

**门店选择方式（与其他爬虫不同）**:
1. 不是直接选择集团账号
2. 需要逐个选择门店：
   - 先选择「集团公司」
   - 下拉选择「品牌」
   - 再下拉选择「具体门店」
3. **每次只能查询一个门店的数据**

### 2.3 页面元素
- 营业日期: 两个日期输入框（开始/结束）
- 门店选择: 下拉框（三级联动）
- 销售方式: 下拉框（单品+套餐明细）
- 统计方式: 按钮组（菜品名称/菜品名称+规格/菜品小类/菜品大类）
- 统计规则: 下拉框（同名菜品合并统计）
- 查询按钮
- 数据表格（需要翻页）

### 2.4 数据字段（从页面观察）
- 菜品名称
- 销售数量
- 销售数量占比
- 销售额(元)
- 销售额占比
- 菜品收入(元)
- 菜品收入占比
- 菜品优惠(元)
- 菜品优惠占比
- 销售额构成（菜品/关联做法/关联加料/关联餐盒）
- 菜品收入构成（菜品/关联做法/关联加料/关联餐盒）

## 3. 数据库设计

### 3.1 SQLite 本地表: `mt_dish_sales`

```sql
CREATE TABLE mt_dish_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,              -- 门店名称
    business_date TEXT NOT NULL,           -- 营业日期 (YYYY-MM-DD)
    dish_name TEXT NOT NULL,               -- 菜品名称
    sales_quantity INTEGER,                -- 销售数量
    sales_quantity_pct REAL,               -- 销售数量占比
    sales_amount REAL,                     -- 销售额(元)
    sales_amount_pct REAL,                 -- 销售额占比
    dish_income REAL,                      -- 菜品收入(元)
    dish_income_pct REAL,                  -- 菜品收入占比
    dish_discount REAL,                    -- 菜品优惠(元)
    dish_discount_pct REAL,                -- 菜品优惠占比
    sales_composition TEXT,                -- 销售额构成(JSON)
    income_composition TEXT,               -- 菜品收入构成(JSON)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 唯一约束
CREATE UNIQUE INDEX idx_dish_sales_unique
ON mt_dish_sales(store_name, business_date, dish_name);

-- 查询索引
CREATE INDEX idx_dish_sales_store_date
ON mt_dish_sales(store_name, business_date);

CREATE INDEX idx_dish_sales_date
ON mt_dish_sales(business_date);
```

### 3.2 Supabase 云端表: `mt_dish_sales`

```sql
CREATE TABLE mt_dish_sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES master_restaurant(id),
    营业日期 DATE NOT NULL,
    菜品名称 TEXT NOT NULL,
    销售数量 INTEGER,
    销售数量占比 NUMERIC,
    销售额 NUMERIC,
    销售额占比 NUMERIC,
    菜品收入 NUMERIC,
    菜品收入占比 NUMERIC,
    菜品优惠 NUMERIC,
    菜品优惠占比 NUMERIC,
    销售额构成 JSONB,
    菜品收入构成 JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 唯一约束
CREATE UNIQUE INDEX idx_dish_sales_unique
ON mt_dish_sales(restaurant_id, 营业日期, 菜品名称);

-- 查询索引
CREATE INDEX idx_dish_sales_restaurant_date
ON mt_dish_sales(restaurant_id, 营业日期);

CREATE INDEX idx_dish_sales_date
ON mt_dish_sales(营业日期);
```

## 4. 爬虫实现设计

### 4.1 文件结构
```
src/crawlers/guanjia/dish_sales.py  # 新建爬虫
```

### 4.2 核心逻辑

```python
class DishSalesCrawler(BaseCrawler):
    """
    菜品销售统计爬虫

    特点:
    1. 需要逐个门店爬取（不能用集团账号一次性获取）
    2. 需要处理三级门店选择（集团→品牌→门店）
    3. 数据在主页面（不在iframe中）
    """

    async def crawl(self, store_id: str = None, store_name: str = None):
        # 1. 获取所有门店列表
        stores = await self._get_store_list()

        # 2. 遍历每个门店
        all_data = []
        for store in stores:
            # 2.1 选择门店
            await self._select_store(store)

            # 2.2 设置日期范围
            await self._set_date_range(self.target_date, self.end_date)

            # 2.3 点击查询
            await self._click_query()

            # 2.4 提取当前门店的所有数据（含翻页）
            store_data = await self._extract_all_pages(store)
            all_data.extend(store_data)

        # 3. 保存到数据库
        save_stats = self.db.save_dish_sales(all_data)

        return self.create_result(True, data={
            "records": all_data,
            "record_count": len(all_data),
            "save_stats": save_stats
        })
```

### 4.3 关键方法

#### 4.3.1 获取门店列表
```python
async def _get_store_list(self) -> List[Dict]:
    """
    从门店下拉框中提取所有门店信息
    返回: [{"group": "集团", "brand": "品牌", "store": "门店名"}]
    """
```

#### 4.3.2 选择门店
```python
async def _select_store(self, store_info: Dict) -> bool:
    """
    三级选择: 集团 → 品牌 → 门店
    """
```

#### 4.3.3 提取表格数据
```python
async def _extract_table_data(self, store_name: str) -> List[Dict]:
    """
    提取当前页的表格数据
    包含: 菜品名称、销售数量、销售额等
    """
```

## 5. 注册到系统

### 5.1 在 `src/sites/meituan_guanjia.py` 中添加:
```python
REPORTS = {
    # ... existing reports ...
    "dish_sales": {
        "name": "菜品销售统计",
        "url": "https://pos.meituan.com/web/report/dish-sale#/rms-report/dishSale",
        "iframe_pattern": None,  # 数据在主页面，不在iframe
        "path": ["报表中心", "菜品报表", "菜品销售统计"]
    }
}
```

### 5.2 在 `src/main.py` 中注册:
```python
from src.crawlers.guanjia.dish_sales import DishSalesCrawler

SITES = {
    "guanjia": {
        # ...
        "reports": {
            # ... existing reports ...
            "dish_sales": DishSalesCrawler
        }
    }
}
```

## 6. 使用方式

```bash
# 爬取单日数据
python src/main.py --report dish_sales --date 2026-01-19

# 爬取日期范围
python src/main.py --report dish_sales --date 2026-01-17 --end-date 2026-01-19

# 爬取所有报表（包括菜品销售）
python src/main.py --report all --date 2026-01-19
```

## 7. 实现注意事项

1. **门店遍历**: 需要获取所有门店列表，逐个查询
2. **日期格式**: 页面使用 `YYYY/MM/DD` 格式，数据库存储 `YYYY-MM-DD`
3. **数据清洗**:
   - 销售数量可能为 0 的菜品（如免费配菜）
   - 百分比需要转换为小数
   - 金额需要去除千分位逗号
4. **翻页处理**: 每个门店的数据可能跨多页
5. **错误处理**: 某个门店失败不应影响其他门店
6. **性能优化**: 考虑并发爬取多个门店（需要多个浏览器tab）

## 8. 数据验证

- 每个门店每天的菜品销售数量总和应该合理
- 销售额 = 菜品收入 + 菜品优惠
- 各项占比之和应该接近 100%

## 9. 后续扩展

- 支持按「菜品名称+规格」统计
- 支持按「菜品小类」或「菜品大类」统计
- 添加菜品销售趋势分析
- 添加菜品排行榜功能
