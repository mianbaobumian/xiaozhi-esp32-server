# xiaozhi_agent 数据库表软删除设计

## 背景

为 `xiaozhi_agent` 数据库的 3 个表增加软删除支持，避免物理删除数据。

## 修改范围

| 表名 | 修改内容 |
|------|----------|
| reminders | 重命名时间字段、新增 updated_time、新增 is_deleted |
| broadcast_queue | 重命名时间字段、新增 updated_time、新增 is_deleted |
| agent_memory | 重命名时间字段、新增 updated_time、新增 is_deleted |

## 字段变更

### 新增字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| is_deleted | TINYINT(1) | 0 | 软删除标志：0=有效，1=无效 |

### 重命名字段

| 原字段名 | 新字段名 | 类型 | 说明 |
|----------|----------|------|------|
| created_at | created_time | DATE | 创建时间 |

### 新增时间字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| updated_time | DATE | NULL | 修改时间，应用层手动维护 |

## SQL 变更语句

```sql
-- reminders 表
ALTER TABLE reminders 
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER status;

-- broadcast_queue 表
ALTER TABLE broadcast_queue
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER status;

-- agent_memory 表
ALTER TABLE agent_memory
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER content;
```

## 代码影响

1. **字段引用更新**：所有 `created_at` 引用需改为 `created_time`
2. **删除逻辑修改**：物理删除改为 `UPDATE ... SET is_deleted=1`
3. **查询条件**：所有查询需加 `WHERE is_deleted=0` 条件
4. **新增字段维护**：代码中需显式设置 `updated_time`

## 注意事项

- `updated_time` 由应用层手动维护，数据库不会自动更新
- 查询时务必加上 `is_deleted=0` 条件，避免查询到已删除数据
