# Agent 会话持久化设计

## Context

当前 `claude -p "task"` 每次调用都是全新进程，CEO 等 agent 没有对话记忆。已验证 `claude -p --resume <uuid>` 可以接续会话。需要一个持久化层存储 session UUID，并支持 24h 自动过期 + 摘要交接。

## 设计概要

- **存储**：Redis（热缓存，TTL 24h）+ MySQL（持久化 + 摘要）
- **维度**：纯 Agent（全局一个 agent 一个会话）
- **过期**：Redis TTL 24h 自动过期，过期后用旧 session 提炼摘要存 MySQL
- **重置**：语音命令 "重置XX会话" 触发摘要 + 新会话

## 数据结构

### Redis

Key: `agent:session:{agent_name}` → session UUID string，TTL 86400s

### MySQL

```sql
CREATE TABLE agent_sessions (
    agent_name VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 核心流程

### 正常调用（Redis 命中）

```
dispatch_to_agent("ceo", "整理成表格")
  → Redis GET agent:session:ceo → "abc-123"
  → claude -p "整理成表格" --resume abc-123
  → 返回结果
```

### Redis 过期（摘要交接）

```
dispatch_to_agent("ceo", "继续上次的工作")
  → Redis GET → 无
  → MySQL SELECT → session_id="abc-123", summary="调研了豆瓣Top5..."
  → prompt = "之前的对话摘要: {summary}\n\n当前任务: 继续上次的工作"
  → 生成新 UUID "def-456"
  → claude -p prompt --session-id def-456
  → Redis SET TTL 24h + MySQL UPDATE session_id
```

### 首次调用（无历史）

```
dispatch_to_agent("ceo", "调研豆瓣Top5")
  → Redis GET → 无
  → MySQL SELECT → 无
  → 生成新 UUID
  → claude -p "调研豆瓣Top5" --session-id <uuid>
  → Redis SET TTL 24h + MySQL INSERT
```

### 手动重置

```
reset_agent_session("ceo")
  → Redis GET → 旧 UUID
  → claude -p "请用3句话总结我们之前的对话要点" --resume <旧uuid>
  → MySQL UPDATE summary = 摘要结果
  → Redis DEL
  → 下次调用自动创建新会话 + 注入摘要
```

### 摘要失败 fallback

如果 `--resume` 失败（session 过久/损坏）：
- 日志 warning，summary 留空或保留旧值
- 仍然创建新会话，不阻塞任务执行
- 不影响核心功能，只是丢失上下文

## 改动文件

### 1. `core/providers/agent_registry/backends/claude_code_backend.py`

修改 `_execute_via_cli`：
- 调用前：从 Redis/MySQL 读取 session UUID
- 存在 → `--resume <uuid>`
- 不存在但有旧摘要 → 注入摘要到 prompt + `--session-id <新uuid>`
- 无历史 → `--session-id <新uuid>`
- 调用后：写入 Redis（TTL 24h）+ UPSERT MySQL

新增辅助方法：
- `_get_session(agent_name) -> (uuid|None, summary|None)`
- `_save_session(agent_name, uuid)`
- `_generate_summary(old_uuid) -> str`

依赖：`from core.utils.db_manager import get_redis_client, execute_query, execute_update`

### 2. `core/providers/agent_registry/agent_proxy.py`

新增方法：
- `async reset_session(agent_name) -> str` — 摘要 + 清除会话

### 3. 新增 `plugins_func/functions/reset_agent_session.py`

注册 `reset_agent_session` 函数，类型 `ToolType.SYSTEM_CTL`。
语音触发词："重置CEO会话"、"清空agent记忆" 等。

### 4. MySQL 建表

在 `xiaozhi_agent` 数据库执行 `agent_sessions.sql`。

## 验证

```bash
# 1. 建表
mysql -u root -p xiaozhi_agent < agent_sessions.sql

# 2. 运行 mock 测试
python verify_ceo_dispatch.py

# 3. 真实测试 - 首次调用
python test_agent_dispatch.py  # CEO 应该创建新会话

# 4. 真实测试 - 接续会话
python test_agent_dispatch.py  # CEO 应该记得上次内容

# 5. 验证 Redis
redis-cli GET agent:session:ceo

# 6. 验证 MySQL
mysql -u root -p xiaozhi_agent -e "SELECT * FROM agent_sessions;"
```
