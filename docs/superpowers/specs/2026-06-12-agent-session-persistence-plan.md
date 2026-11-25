# Agent 会话持久化实施计划

设计文档：[2026-06-12-agent-session-persistence-design.md](./2026-06-12-agent-session-persistence-design.md)

## 步骤

### 1. MySQL 建表

- [x] 创建 `agent_sessions.sql` 建表脚本
- [x] 在 `xiaozhi_agent` 数据库执行建表

**验证：** `SELECT COUNT(*) FROM agent_sessions` 不报错

### 2. 改造 `claude_code_backend.py`

- [x] 新增 `_get_session(agent_name)` — 从 Redis/MySQL 读取 session UUID + 摘要
- [x] 新增 `_save_session(agent_name, uuid)` — 写入 Redis (TTL 24h) + MySQL UPSERT
- [x] 新增 `_save_summary(agent_name, summary)` — 更新 MySQL 摘要
- [x] 新增 `_generate_summary(old_uuid)` — 用旧 session 调 CLI 提炼摘要
- [x] 新增 `_run_cli(cmd, args, ...)` — 抽取 CLI 子进程执行逻辑
- [x] 改造 `_execute_via_cli` — 集成 session 读写 + 摘要注入

**验证：** `verify_ceo_dispatch.py` 6 个 mock 测试全部 PASS

### 3. 改造 `agent_proxy.py`

- [x] 新增 `reset_session(agent_name)` 方法 — 调用 backend 的 reset_session

**验证：** import 不报错，方法存在

### 4. 新增 `reset_agent_session.py` 插件

- [x] 创建 `plugins_func/functions/reset_agent_session.py`
- [x] 注册 `reset_agent_session` 函数，类型 `ToolType.SYSTEM_CTL`

**验证：** `from plugins_func.functions.reset_agent_session import reset_agent_session` 不报错

### 5. 真实端到端测试

- [ ] 首次调用 CEO → 验证 Redis/MySQL 写入了 session UUID
- [ ] 第二次调用 CEO → 验证 `--resume` 接续会话，CEO 记得上次内容
- [ ] 调用 `reset_agent_session("ceo")` → 验证摘要生成 + Redis 清除
- [ ] 重置后再次调用 → 验证新会话带摘要上下文

**验证命令：**
```bash
# 检查 Redis
redis-cli GET agent:session:ceo

# 检查 MySQL
mysql -u root -p xiaozhi_agent -e "SELECT * FROM agent_sessions;"

# 运行测试
python test_agent_dispatch.py
```

## 改动文件清单

| 文件 | 操作 | 状态 |
|------|------|------|
| `agent_sessions.sql` | 新增 | done |
| `core/providers/agent_registry/backends/claude_code_backend.py` | 改造 | done |
| `core/providers/agent_registry/agent_proxy.py` | 新增方法 | done |
| `plugins_func/functions/reset_agent_session.py` | 新增 | done |
| `verify_ceo_dispatch.py` | 已有 mock 测试 | pass |
