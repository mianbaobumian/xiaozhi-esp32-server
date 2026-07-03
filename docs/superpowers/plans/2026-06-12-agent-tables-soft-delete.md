# xiaozhi_agent 数据库表软删除实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 xiaozhi_agent 数据库的 3 个表（reminders、broadcast_queue、agent_memory）增加软删除支持，将 `created_at` 重命名为 `created_time`，新增 `updated_time` 和 `is_deleted` 字段。

**Architecture:** 修改建表 SQL 脚本，更新所有引用这些表的 Python 代码中的字段名和查询条件。删除操作改为设置 `is_deleted=1`，查询时需加 `WHERE is_deleted=0` 条件。

**Tech Stack:** Python 3.10, MySQL, pymysql

---

## 修改范围

### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `data/migrations/001_create_agent_tables.sql` | 修改建表语句 |
| `core/providers/scheduler/reminder_store.py` | 修改 reminders 表的 SQL |
| `core/providers/broadcast/broadcast_manager.py` | 修改 broadcast_queue 表的 SQL |
| `core/providers/scheduler/scheduler_manager.py` | 修改 broadcast_queue 的 INSERT 语句 |

### 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `plugins_func/functions/list_reminders.py` | 调用 ReminderStore 方法，无直接 SQL |
| `plugins_func/functions/query_schedule.py` | 调用 ReminderStore 方法，无直接 SQL |
| `plugins_func/functions/delete_reminder.py` | 调用 ReminderStore.delete()，无直接 SQL |
| `core/connection.py` | 调用 ReminderStore.get_all_active()，无直接 SQL |

---

### Task 1: 修改建表 SQL 脚本

**Files:**
- Modify: `data/migrations/001_create_agent_tables.sql`

- [ ] **Step 1: 修改 reminders 表定义**

将 `created_at` 改为 `created_time`，新增 `updated_time` 和 `is_deleted` 字段：

```sql
CREATE TABLE IF NOT EXISTS reminders (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    trigger_type VARCHAR(16) NOT NULL,
    trigger_time VARCHAR(64),
    message TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    created_time DATE NOT NULL,
    updated_time DATE DEFAULT NULL,
    is_deleted TINYINT(1) DEFAULT 0,
    fired_at DATETIME,
    INDEX idx_device_status (device_id, status)
);
```

- [ ] **Step 2: 修改 broadcast_queue 表定义**

将 `created_at` 改为 `created_time`，新增 `updated_time` 和 `is_deleted` 字段：

```sql
CREATE TABLE IF NOT EXISTS broadcast_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    created_time DATE NOT NULL,
    updated_time DATE DEFAULT NULL,
    is_deleted TINYINT(1) DEFAULT 0,
    delivered_at DATETIME,
    INDEX idx_status_priority (status, priority)
);
```

- [ ] **Step 3: 修改 agent_memory 表定义**

将 `created_at` 改为 `created_time`，新增 `updated_time` 和 `is_deleted` 字段：

```sql
CREATE TABLE IF NOT EXISTS agent_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    created_time DATE NOT NULL,
    updated_time DATE DEFAULT NULL,
    is_deleted TINYINT(1) DEFAULT 0,
    INDEX idx_agent_time (agent_name, created_time)
);
```

- [ ] **Step 4: Commit**

```bash
git add data/migrations/001_create_agent_tables.sql
git commit -m "feat: 更新建表脚本，支持软删除"
```

---

### Task 2: 修改 reminder_store.py

**Files:**
- Modify: `core/providers/scheduler/reminder_store.py`

- [ ] **Step 1: 修改 save 方法**

将 `created_at` 改为 `created_time`：

```python
def save(self, device_id: str, trigger_type: str, trigger_time: str, message: str) -> str:
    reminder_id = str(uuid.uuid4())
    sql = """
        INSERT INTO reminders (id, device_id, trigger_type, trigger_time, message, status, created_time)
        VALUES (%s, %s, %s, %s, %s, 'active', %s)
    """
    execute_update(sql, (reminder_id, device_id, trigger_type, trigger_time, message, datetime.now().date()))
    logger.bind(tag=TAG).info(f"保存提醒: {reminder_id}, 消息: {message}")
    return reminder_id
```

- [ ] **Step 2: 修改 get_active_reminders 方法**

将 `created_at` 改为 `created_time`，添加 `is_deleted=0` 条件：

```python
def get_active_reminders(self, device_id: str) -> list:
    sql = "SELECT * FROM reminders WHERE device_id = %s AND status = 'active' AND is_deleted = 0 ORDER BY created_time"
    return execute_query(sql, (device_id,))
```

- [ ] **Step 3: 修改 get_all_active 方法**

添加 `is_deleted=0` 条件：

```python
def get_all_active(self) -> list:
    sql = "SELECT * FROM reminders WHERE status = 'active' AND is_deleted = 0"
    return execute_query(sql)
```

- [ ] **Step 4: 修改 delete 方法**

将 `status = 'deleted'` 改为 `is_deleted = 1`，并设置 `updated_time`：

```python
def delete(self, reminder_id: str):
    sql = "UPDATE reminders SET is_deleted = 1, updated_time = %s WHERE id = %s"
    execute_update(sql, (datetime.now().date(), reminder_id))
```

- [ ] **Step 5: Commit**

```bash
git add core/providers/scheduler/reminder_store.py
git commit -m "feat: 更新 reminder_store 支持软删除"
```

---

### Task 3: 修改 broadcast_manager.py

**Files:**
- Modify: `core/providers/broadcast/broadcast_manager.py`

- [ ] **Step 1: 修改 _process_pending_messages 方法**

将 `created_at` 改为 `created_time`，添加 `is_deleted=0` 条件：

```python
def _process_pending_messages(self):
    sql = """
        SELECT * FROM broadcast_queue
        WHERE status = 'pending' AND is_deleted = 0
        ORDER BY
            CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END,
            created_time
        LIMIT 10
    """
    messages = execute_query(sql)
    for msg in messages:
        success = self._deliver_message(msg)
        if success:
            execute_update(
                "UPDATE broadcast_queue SET status = 'delivered', delivered_at = %s, updated_time = %s WHERE id = %s",
                (datetime.now(), datetime.now().date(), msg["id"]),
            )
        else:
            execute_update(
                "UPDATE broadcast_queue SET retry_count = retry_count + 1, updated_time = %s WHERE id = %s",
                (datetime.now().date(), msg["id"]),
            )
```

- [ ] **Step 2: 修改 enqueue 方法**

将 `created_at` 改为 `created_time`：

```python
def enqueue(self, source: str, priority: str, content: str):
    sql = """
        INSERT INTO broadcast_queue (source, priority, content, status, created_time)
        VALUES (%s, %s, %s, 'pending', %s)
    """
    execute_update(sql, (source, priority, content, datetime.now().date()))
    redis_client = get_redis_client()
    redis_client.publish("broadcast:notify", json.dumps({"source": source}))
    logger.bind(tag=TAG).info(f"消息入队: source={source}, priority={priority}")
```

- [ ] **Step 3: Commit**

```bash
git add core/providers/broadcast/broadcast_manager.py
git commit -m "feat: 更新 broadcast_manager 支持软删除"
```

---

### Task 4: 修改 scheduler_manager.py

**Files:**
- Modify: `core/providers/scheduler/scheduler_manager.py`

- [ ] **Step 1: 修改 _fire_reminder 方法**

将 `created_at` 改为 `created_time`：

```python
def _fire_reminder(self, job_id: str, message: str, device_id: str):
    try:
        sql = """
            INSERT INTO broadcast_queue (source, priority, content, status, created_time)
            VALUES ('scheduler', 'normal', %s, 'pending', %s)
        """
        execute_update(sql, (message, datetime.now().date()))
        redis_client = get_redis_client()
        redis_client.publish("broadcast:notify", json.dumps({"source": "scheduler"}))
        from core.providers.scheduler.reminder_store import ReminderStore
        store = ReminderStore()
        store.mark_fired(job_id)
        logger.bind(tag=TAG).info(f"提醒已触发: {job_id}, 消息: {message}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"触发提醒失败: {job_id}, {e}")
```

- [ ] **Step 2: Commit**

```bash
git add core/providers/scheduler/scheduler_manager.py
git commit -m "feat: 更新 scheduler_manager 支持软删除"
```

---

### Task 5: 添加数据库迁移脚本

**Files:**
- Create: `data/migrations/002_add_soft_delete_support.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- 为现有数据库添加软删除支持
USE xiaozhi_agent;

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

- [ ] **Step 2: Commit**

```bash
git add data/migrations/002_add_soft_delete_support.sql
git commit -m "feat: 添加软删除支持的数据库迁移脚本"
```

---

## 验证步骤

1. **检查 SQL 语法**：确认所有 SQL 语句语法正确
2. **检查代码一致性**：确认所有 `created_at` 引用已改为 `created_time`
3. **检查软删除逻辑**：确认删除操作改为 `SET is_deleted=1`
4. **检查查询条件**：确认所有查询都添加了 `is_deleted=0` 条件

## 注意事项

- `updated_time` 由应用层手动维护，需要在每次 UPDATE 时显式设置
- 查询时务必加上 `is_deleted=0` 条件，避免查询到已删除数据
- `datetime.now().date()` 返回 DATE 类型，与数据库 DATE 字段匹配
