# Supabase 数据库表设计 - 菜品销售统计

## 现有表结构概览

### 1. master_restaurant (餐厅主表)
```sql
CREATE TABLE master_restaurant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_name TEXT,
    meituan_org_code TEXT,  -- 美团机构编码 (如 MD00012)
    -- ... 其他字段
);
```
**作用**: 所有美团数据的核心映射表，通过 `meituan_org_code` 关联美团数据

### 2. mt_equity_package_sales (权益包销售)
```sql
CREATE TABLE mt_equity_package_sales (
    id UUID PRIMARY KEY,
    restaurant_id UUID REFERENCES master_restaurant(id),  -- 关联餐厅
    date DATE,
    package_name TEXT,
    quantity_sold INTEGER,
    total_sales NUMERIC,
    -- ...
    UNIQUE(restaurant_id, date, package_name)
);
```

### 3. mt_business_summary (综合营业统计)
```sql
CREATE TABLE mt_business_summary (
    id UUID PRIMARY KEY,
    restaurant_id UUID REFERENCES master_restaurant(id),  -- 关联餐厅
    营业日期 DATE,
    营业额 NUMERIC,
    订单数 INTEGER,
    -- ...
    UNIQUE(restaurant_id, 营业日期)
);
```

## 表关系图

```
master_restaurant (id, meituan_org_code, restaurant_name)
    ↓ (1:N)
    ├── mt_equity_package_sales (restaurant_id, date, package_name)
    ├── mt_business_summary (restaurant_id, 营业日期)
    └── mt_dish_sales (restaurant_id, 营业日期, 菜品名称)  ← 新表
```

---

## 新表设计: mt_dish_sales (菜品销售统计)

### 表结构

```sql
CREATE TABLE mt_dish_sales (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联字段
    restaurant_id UUID NOT NULL REFERENCES master_restaurant(id) ON DELETE CASCADE,

    -- 业务主键
    营业日期 DATE NOT NULL,
    菜品名称 TEXT NOT NULL,

    -- 销售基础数据
    销售数量 INTEGER,                    -- 实际销售数量
    销售数量占比 NUMERIC(5,2),           -- 百分比
    折前均价 NUMERIC(10,2),              -- 折扣前平均价格
    折后均价 NUMERIC(10,2),              -- 折扣后平均价格
    销售额 NUMERIC(10,2),                -- 总销售额
    销售额占比 NUMERIC(5,2),             -- 百分比

    -- 优惠数据
    优惠金额 NUMERIC(10,2),              -- 折扣金额
    菜品优惠占比 NUMERIC(5,2),           -- 百分比
    菜品收入 NUMERIC(10,2),              -- 实际收入 (销售额 - 优惠)
    菜品收入占比 NUMERIC(5,2),           -- 百分比

    -- 点菜数据
    点菜数量 INTEGER,                    -- 点菜总数 (包括退菜)
    点菜金额 NUMERIC(10,2),              -- 点菜总金额

    -- 退菜数据
    退菜数量 INTEGER,                    -- 退菜数量
    退菜金额 NUMERIC(10,2),              -- 退菜金额
    退菜数量占比 NUMERIC(5,2),           -- 百分比
    退菜金额占比 NUMERIC(5,2),           -- 百分比
    退菜率 NUMERIC(5,2),                 -- 退菜率百分比
    退菜订单量 INTEGER,                  -- 有退菜的订单数

    -- 赠菜数据
    赠菜数量 INTEGER,                    -- 赠送数量
    赠菜金额 NUMERIC(10,2),              -- 赠送金额
    赠菜数量占比 NUMERIC(5,2),           -- 百分比
    赠菜金额占比 NUMERIC(5,2),           -- 百分比

    -- 订单统计
    菜品销售订单量 INTEGER,              -- 包含该菜品的订单数
    关联订单金额 NUMERIC(10,2),          -- 这些订单的总金额
    菜品销售千次 NUMERIC(10,2),          -- 每千次的销售量
    菜品点单率 NUMERIC(5,2),             -- 点单率百分比
    顾客点击率 NUMERIC(5,2),             -- 顾客点击率百分比

    -- 审计字段
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 唯一约束: 每个餐厅每天每个菜品只有一条记录
CREATE UNIQUE INDEX idx_dish_sales_unique
ON mt_dish_sales(restaurant_id, 营业日期, 菜品名称);

-- 查询优化索引
CREATE INDEX idx_dish_sales_restaurant_date
ON mt_dish_sales(restaurant_id, 营业日期);

CREATE INDEX idx_dish_sales_date
ON mt_dish_sales(营业日期);

CREATE INDEX idx_dish_sales_dish_name
ON mt_dish_sales(菜品名称);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_mt_dish_sales_updated_at
BEFORE UPDATE ON mt_dish_sales
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 表注释

```sql
COMMENT ON TABLE mt_dish_sales IS '菜品销售统计 - 每个餐厅每天每个菜品的详细销售数据';
COMMENT ON COLUMN mt_dish_sales.restaurant_id IS '关联 master_restaurant.id';
COMMENT ON COLUMN mt_dish_sales.营业日期 IS '营业日期';
COMMENT ON COLUMN mt_dish_sales.菜品名称 IS '菜品名称 (已合并同名菜品)';
COMMENT ON COLUMN mt_dish_sales.销售数量 IS '实际销售数量 (点菜 - 退菜 - 赠菜)';
COMMENT ON COLUMN mt_dish_sales.点菜数量 IS '点菜总数 (包括后续退菜的)';
COMMENT ON COLUMN mt_dish_sales.退菜率 IS '退菜率 = 退菜数量 / 点菜数量 * 100%';
```

---

## 数据关系说明

### 1. 与 master_restaurant 的关系
```sql
-- 通过 restaurant_id 关联
SELECT
    r.restaurant_name,
    r.meituan_org_code,
    d.菜品名称,
    d.销售数量,
    d.销售额
FROM mt_dish_sales d
JOIN master_restaurant r ON d.restaurant_id = r.id
WHERE d.营业日期 = '2026-01-19';
```

### 2. 与其他美团表的关系
```sql
-- 综合查询: 某餐厅某天的营业概况 + 菜品明细
SELECT
    r.restaurant_name,
    bs.营业额 as total_revenue,
    bs.订单数 as total_orders,
    d.菜品名称,
    d.销售数量,
    d.销售额
FROM master_restaurant r
LEFT JOIN mt_business_summary bs
    ON r.id = bs.restaurant_id AND bs.营业日期 = '2026-01-19'
LEFT JOIN mt_dish_sales d
    ON r.id = d.restaurant_id AND d.营业日期 = '2026-01-19'
WHERE r.meituan_org_code IN ('MD00012', 'MD00010');
```

---

## 数据验证规则

### 1. 数值关系验证
```sql
-- 销售数量 = 点菜数量 - 退菜数量 - 赠菜数量
CHECK (销售数量 = 点菜数量 - COALESCE(退菜数量, 0) - COALESCE(赠菜数量, 0))

-- 销售额 = 菜品收入 + 优惠金额
CHECK (ABS(销售额 - (菜品收入 + COALESCE(优惠金额, 0))) < 0.01)

-- 退菜率计算验证
CHECK (点菜数量 = 0 OR ABS(退菜率 - (退菜数量::NUMERIC / 点菜数量 * 100)) < 0.01)
```

### 2. 占比验证
```sql
-- 所有占比字段应该在 0-100 之间
CHECK (销售数量占比 >= 0 AND 销售数量占比 <= 100)
CHECK (销售额占比 >= 0 AND 销售额占比 <= 100)
-- ... 其他占比字段
```

---

## 数据迁移和初始化

### 1. 创建表
```sql
-- 在 Supabase SQL Editor 中执行上述 CREATE TABLE 语句
```

### 2. 授权
```sql
-- 允许 service_role 访问
GRANT ALL ON mt_dish_sales TO service_role;

-- 如果需要 anon/authenticated 访问，添加 RLS 策略
ALTER TABLE mt_dish_sales ENABLE ROW LEVEL SECURITY;

-- 示例策略: 允许读取
CREATE POLICY "Allow read access" ON mt_dish_sales
FOR SELECT USING (true);
```

### 3. 验证表创建
```sql
-- 检查表结构
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'mt_dish_sales'
ORDER BY ordinal_position;

-- 检查索引
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'mt_dish_sales';

-- 检查外键
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'mt_dish_sales' AND tc.constraint_type = 'FOREIGN KEY';
```

---

## 使用示例

### 1. 插入数据
```sql
INSERT INTO mt_dish_sales (
    restaurant_id, 营业日期, 菜品名称,
    销售数量, 销售额, 菜品收入, 优惠金额
) VALUES (
    (SELECT id FROM master_restaurant WHERE meituan_org_code = 'MD00012'),
    '2026-01-19',
    '非遗手工蘸料',
    146, 685.54, 668.59, 16.95
)
ON CONFLICT (restaurant_id, 营业日期, 菜品名称)
DO UPDATE SET
    销售数量 = EXCLUDED.销售数量,
    销售额 = EXCLUDED.销售额,
    updated_at = NOW();
```

### 2. 查询热销菜品
```sql
SELECT
    r.restaurant_name,
    d.菜品名称,
    SUM(d.销售数量) as total_quantity,
    SUM(d.销售额) as total_amount
FROM mt_dish_sales d
JOIN master_restaurant r ON d.restaurant_id = r.id
WHERE d.营业日期 BETWEEN '2026-01-01' AND '2026-01-31'
GROUP BY r.restaurant_name, d.菜品名称
ORDER BY total_quantity DESC
LIMIT 10;
```

### 3. 分析退菜率
```sql
SELECT
    r.restaurant_name,
    d.菜品名称,
    AVG(d.退菜率) as avg_return_rate,
    SUM(d.退菜数量) as total_returns
FROM mt_dish_sales d
JOIN master_restaurant r ON d.restaurant_id = r.id
WHERE d.营业日期 >= CURRENT_DATE - INTERVAL '30 days'
    AND d.退菜率 > 5  -- 退菜率超过5%
GROUP BY r.restaurant_name, d.菜品名称
ORDER BY avg_return_rate DESC;
```

---

## 存储估算

### 单条记录大小
- UUID: 16 bytes
- DATE: 4 bytes
- TEXT (菜品名称, 平均50字符): ~50 bytes
- NUMERIC 字段 (30个): ~30 * 8 = 240 bytes
- INTEGER 字段 (8个): 8 * 4 = 32 bytes
- TIMESTAMPTZ (2个): 2 * 8 = 16 bytes

**总计**: ~358 bytes/record

### 容量估算
- 每天每个餐厅约 50-100 个菜品
- 8 个餐厅 × 80 菜品/天 × 365 天 = 233,600 records/year
- 存储: 233,600 × 358 bytes ≈ 84 MB/year

**结论**: 存储需求很小，性能不是问题
