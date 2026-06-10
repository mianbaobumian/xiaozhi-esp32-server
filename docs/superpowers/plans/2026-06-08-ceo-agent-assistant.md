# CEO Agent 智能助手实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ESP32 设备升级为个人智能助手，通过 CEO Agent 架构实现语音提醒、任务管理、Agent 调度等功能。

**Architecture:** CEO Agent (Claude Code) 作为决策中心，通过 Multica（执行引擎）、Gitea（看板）、OpenClaw（助理）三种后端管理任务。消息队列使用 MySQL 持久化 + Redis 实时通知。

**Tech Stack:** Python 3.10, APScheduler, MySQL, Redis, MCP, Claude Code

---

## 文件结构

### 新建文件

| 路径 | 职责 |
|------|------|
| `main/xiaozhi-server/core/providers/scheduler/__init__.py` | 模块入口 |
| `main/xiaozhi-server/core/providers/scheduler/scheduler_manager.py` | APScheduler 封装 |
| `main/xiaozhi-server/core/providers/scheduler/reminder_store.py` | MySQL 持久化提醒 |
| `main/xiaozhi-server/core/providers/broadcast/__init__.py` | 模块入口 |
| `main/xiaozhi-server/core/providers/broadcast/broadcast_manager.py` | Redis 订阅 + MySQL 读取 |
| `main/xiaozhi-server/core/providers/broadcast/message_handler.py` | 优先级处理 + 空闲检测 |
| `main/xiaozhi-server/core/providers/agent_registry/__init__.py` | 模块入口 |
| `main/xiaozhi-server/core/providers/agent_registry/registry.py` | 扫描 workspace 加载 agent |
| `main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py` | 后端路由代理 |
| `main/xiaozhi-server/core/providers/context_manager/__init__.py` | 模块入口 |
| `main/xiaozhi-server/core/providers/context_manager/context_manager.py` | 上下文压缩 |
| `main/xiaozhi-server/core/providers/context_manager/summarizer.py` | LLM 摘要 |
| `main/xiaozhi-server/plugins_func/functions/set_reminder.py` | 设置提醒插件 |
| `main/xiaozhi-server/plugins_func/functions/list_reminders.py` | 查询提醒插件 |
| `main/xiaozhi-server/plugins_func/functions/delete_reminder.py` | 删除提醒插件 |
| `main/xiaozhi-server/plugins_func/functions/list_agents.py` | 列出 Agent 插件 |
| `main/xiaozhi-server/plugins_func/functions/query_agent_tasks.py` | 查询任务插件 |
| `main/xiaozhi-server/plugins_func/functions/dispatch_to_agent.py` | 分发任务插件 |
| `main/xiaozhi-server/plugins_func/functions/agent_health_check.py` | 健康巡检插件 |
| `main/xiaozhi-server/workspace/backends.yaml` | 后端配置 |
| `main/xiaozhi-server/workspace/ceo/config.yaml` | CEO 配置 |
| `main/xiaozhi-server/workspace/pm/config.yaml` | PM 配置 |
| `main/xiaozhi-server/workspace/broadcast/config.yaml` | 播报配置 |
| `main/xiaozhi-server/workspace/agents/executor/config.yaml` | 执行 agent 配置 |
| `main/xiaozhi-server/workspace/agents/reviewer/config.yaml` | 审查 agent 配置 |
| `main/xiaozhi-server/workspace/agents/assistant/config.yaml` | 助理 agent 配置 |
| `main/xiaozhi-server/data/migrations/001_create_agent_tables.sql` | MySQL 建表脚本 |

### 修改文件

| 路径 | 修改内容 |
|------|----------|
| `main/xiaozhi-server/config/config_loader.py` | 新增 `load_backends_config()` 函数 |
| `main/xiaozhi-server/core/utils/prompt_manager.py` | `update_context_info()` 注入 Agent 列表 |
| `main/xiaozhi-server/core/connection.py` | `_initialize_components()` 初始化新模块 |

---

## Phase 1: 基础框架

### Task 1.1: 创建 workspace 目录结构

**Files:**
- Create: `main/xiaozhi-server/workspace/backends.yaml`
- Create: `main/xiaozhi-server/workspace/ceo/config.yaml`
- Create: `main/xiaozhi-server/workspace/pm/config.yaml`
- Create: `main/xiaozhi-server/workspace/broadcast/config.yaml`
- Create: `main/xiaozhi-server/workspace/agents/executor/config.yaml`
- Create: `main/xiaozhi-server/workspace/agents/reviewer/config.yaml`
- Create: `main/xiaozhi-server/workspace/agents/assistant/config.yaml`

- [ ] **Step 1: 创建 backends.yaml**

```yaml
# main/xiaozhi-server/workspace/backends.yaml
workspace_path: ./workspace

mysql:
  host: localhost
  port: 3306
  database: xiaozhi_agent
  user: root
  password: ""

redis:
  host: localhost
  port: 6379
  db: 3
  password: null

gitea:
  url: http://192.168.31.179:8418
  repo: ""
  token: ""

multica:
  url: http://192.168.31.179:18080
  api_key: ""
  project: ""

claude_code:
  type: mcp
  command: claude
  args: ["mcp", "serve"]

openclaw:
  type: http
  url: http://192.168.31.179:18789
  workspace: /home/dapao/.openclaw
  role: assistant
```

- [ ] **Step 2: 创建 CEO config.yaml**

```yaml
# main/xiaozhi-server/workspace/ceo/config.yaml
name: CEO
description: 私人助手，决策中心
backend: claude_code
model: claude-opus-4-7
context_window: 200000
compression_threshold: 0.5
enabled: true
schedule:
  morning_briefing: "08:00"
  evening_summary: "22:00"
  health_check_interval: 3600
```

- [ ] **Step 3: 创建 PM config.yaml**

```yaml
# main/xiaozhi-server/workspace/pm/config.yaml
name: Claude-PM
description: 项目级管理，Claude 子代理执行，双写 Gitea + Multica 看板
backend: claude_code
model: claude-sonnet-4-6
enabled: true
```

- [ ] **Step 4: 创建 Broadcast config.yaml**

```yaml
# main/xiaozhi-server/workspace/broadcast/config.yaml
name: Broadcast
description: 专职 TTS 播报
backend: local
enabled: true
redis_channel: "broadcast:notify"
redis_db: 3
priority_levels:
  high: immediate
  normal: queue
  low: idle
```

- [ ] **Step 5: 创建下属 agent config.yaml**

```yaml
# main/xiaozhi-server/workspace/agents/executor/config.yaml
name: executor
description: 代码实现、重构、bug 修复
backend: multica
backend_id: ""
model: null
enabled: true
```

```yaml
# main/xiaozhi-server/workspace/agents/reviewer/config.yaml
name: reviewer
description: 代码审查、质量检查
backend: multica
backend_id: ""
model: null
enabled: true
```

```yaml
# main/xiaozhi-server/workspace/agents/assistant/config.yaml
name: assistant
description: 个人助理，网上找资料、GitHub 信息对比筛选
backend: openclaw
backend_id: ""
model: null
enabled: true
```

- [ ] **Step 6: Commit**

```bash
git add main/xiaozhi-server/workspace/
git commit -m "feat: create workspace directory structure with agent configs"
```

---

### Task 1.2: MySQL 建表脚本

**Files:**
- Create: `main/xiaozhi-server/data/migrations/001_create_agent_tables.sql`

- [ ] **Step 1: 创建 SQL 迁移脚本**

```sql
-- main/xiaozhi-server/data/migrations/001_create_agent_tables.sql
CREATE DATABASE IF NOT EXISTS xiaozhi_agent DEFAULT CHARACTER SET utf8mb4;
USE xiaozhi_agent;

CREATE TABLE IF NOT EXISTS reminders (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    trigger_type VARCHAR(16) NOT NULL,
    trigger_time VARCHAR(64),
    message TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    created_at DATETIME NOT NULL,
    fired_at DATETIME,
    INDEX idx_device_status (device_id, status)
);

CREATE TABLE IF NOT EXISTS broadcast_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    created_at DATETIME NOT NULL,
    delivered_at DATETIME,
    INDEX idx_status_priority (status, priority)
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    created_at DATETIME NOT NULL,
    INDEX idx_agent_time (agent_name, created_at)
);
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/data/migrations/
git commit -m "feat: add MySQL migration for agent tables"
```

---

### Task 1.3: 实现 backends.yaml 配置加载

**Files:**
- Modify: `main/xiaozhi-server/config/config_loader.py`

- [ ] **Step 1: 在 config_loader.py 中添加 load_backends_config 函数**

在文件末尾添加：

```python
def load_backends_config():
    """加载 backends.yaml 配置"""
    from core.utils.cache.manager import cache_manager, CacheType

    cached = cache_manager.get(CacheType.CONFIG, "backends_config")
    if cached is not None:
        return cached

    backends_path = os.path.join(get_project_dir(), "workspace", "backends.yaml")
    if not os.path.exists(backends_path):
        return {}

    config = read_config(backends_path)
    cache_manager.set(CacheType.CONFIG, "backends_config", config)
    return config
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/config/config_loader.py
git commit -m "feat: add load_backends_config for workspace configuration"
```

---

### Task 1.4: 实现 MySQL 和 Redis 连接工具

**Files:**
- Create: `main/xiaozhi-server/core/utils/db_manager.py`

- [ ] **Step 1: 创建数据库管理器**

```python
# main/xiaozhi-server/core/utils/db_manager.py
"""MySQL 和 Redis 连接管理"""
import json
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

_mysql_conn = None
_redis_client = None


def get_mysql_connection():
    """获取 MySQL 连接"""
    global _mysql_conn
    if _mysql_conn is not None:
        return _mysql_conn

    from config.config_loader import load_backends_config
    import pymysql

    config = load_backends_config()
    mysql_config = config.get("mysql", {})

    _mysql_conn = pymysql.connect(
        host=mysql_config.get("host", "localhost"),
        port=mysql_config.get("port", 3306),
        user=mysql_config.get("user", "root"),
        password=mysql_config.get("password", ""),
        database=mysql_config.get("database", "xiaozhi_agent"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    logger.bind(tag=TAG).info("MySQL 连接成功")
    return _mysql_conn


def get_redis_client():
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    from config.config_loader import load_backends_config
    import redis

    config = load_backends_config()
    redis_config = config.get("redis", {})

    _redis_client = redis.Redis(
        host=redis_config.get("host", "localhost"),
        port=redis_config.get("port", 6379),
        db=redis_config.get("db", 3),
        password=redis_config.get("password"),
        decode_responses=True,
    )
    logger.bind(tag=TAG).info("Redis 连接成功")
    return _redis_client


def execute_query(sql, params=None):
    """执行查询语句"""
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def execute_update(sql, params=None):
    """执行更新语句"""
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        result = cursor.execute(sql, params)
    conn.commit()
    return result
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/utils/db_manager.py
git commit -m "feat: add MySQL and Redis connection manager"
```

---

## Phase 2: Scheduler 模块

### Task 2.1: 实现 ReminderStore

**Files:**
- Create: `main/xiaozhi-server/core/providers/scheduler/__init__.py`
- Create: `main/xiaozhi-server/core/providers/scheduler/reminder_store.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# main/xiaozhi-server/core/providers/scheduler/__init__.py
from .scheduler_manager import SchedulerManager
from .reminder_store import ReminderStore

__all__ = ["SchedulerManager", "ReminderStore"]
```

- [ ] **Step 2: 创建 reminder_store.py**

```python
# main/xiaozhi-server/core/providers/scheduler/reminder_store.py
"""MySQL 持久化提醒任务"""
import uuid
from datetime import datetime
from core.utils.db_manager import execute_query, execute_update
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ReminderStore:
    def save(self, device_id: str, trigger_type: str, trigger_time: str, message: str) -> str:
        """保存提醒任务"""
        reminder_id = str(uuid.uuid4())
        sql = """
            INSERT INTO reminders (id, device_id, trigger_type, trigger_time, message, status, created_at)
            VALUES (%s, %s, %s, %s, %s, 'active', %s)
        """
        execute_update(sql, (reminder_id, device_id, trigger_type, trigger_time, message, datetime.now()))
        logger.bind(tag=TAG).info(f"保存提醒: {reminder_id}, 消息: {message}")
        return reminder_id

    def get_active_reminders(self, device_id: str) -> list:
        """获取活跃提醒"""
        sql = "SELECT * FROM reminders WHERE device_id = %s AND status = 'active' ORDER BY created_at"
        return execute_query(sql, (device_id,))

    def get_all_active(self) -> list:
        """获取所有活跃提醒（启动恢复用）"""
        sql = "SELECT * FROM reminders WHERE status = 'active'"
        return execute_query(sql)

    def mark_fired(self, reminder_id: str):
        """标记为已触发"""
        sql = "UPDATE reminders SET status = 'fired', fired_at = %s WHERE id = %s"
        execute_update(sql, (datetime.now(), reminder_id))

    def delete(self, reminder_id: str):
        """删除提醒"""
        sql = "UPDATE reminders SET status = 'deleted' WHERE id = %s"
        execute_update(sql, (reminder_id,))
```

- [ ] **Step 3: Commit**

```bash
git add main/xiaozhi-server/core/providers/scheduler/
git commit -m "feat: implement ReminderStore for MySQL persistence"
```

---

### Task 2.2: 实现 SchedulerManager

**Files:**
- Create: `main/xiaozhi-server/core/providers/scheduler/scheduler_manager.py`

- [ ] **Step 1: 创建 scheduler_manager.py**

```python
# main/xiaozhi-server/core/providers/scheduler/scheduler_manager.py
"""APScheduler 封装，管理定时任务"""
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from core.utils.db_manager import execute_update, get_redis_client
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.bind(tag=TAG).info("SchedulerManager 已启动")

    def add_once_job(self, job_id: str, run_date: datetime, message: str, device_id: str):
        """添加一次性任务"""
        trigger = DateTrigger(run_date=run_date)
        self.scheduler.add_job(
            self._fire_reminder,
            trigger=trigger,
            id=job_id,
            args=[job_id, message, device_id],
            replace_existing=True,
        )
        logger.bind(tag=TAG).info(f"添加一次性任务: {job_id}, 时间: {run_date}")

    def add_cron_job(self, job_id: str, cron_expr: str, message: str, device_id: str):
        """添加周期性任务"""
        parts = cron_expr.split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
        )
        self.scheduler.add_job(
            self._fire_reminder,
            trigger=trigger,
            id=job_id,
            args=[job_id, message, device_id],
            replace_existing=True,
        )
        logger.bind(tag=TAG).info(f"添加周期任务: {job_id}, cron: {cron_expr}")

    def remove_job(self, job_id: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.bind(tag=TAG).info(f"移除任务: {job_id}")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"移除任务失败: {job_id}, {e}")

    def _fire_reminder(self, job_id: str, message: str, device_id: str):
        """触发提醒：写入 MySQL + 通知 Redis"""
        try:
            # 写入 broadcast_queue
            sql = """
                INSERT INTO broadcast_queue (source, priority, content, status, created_at)
                VALUES ('scheduler', 'normal', %s, 'pending', %s)
            """
            execute_update(sql, (message, datetime.now()))

            # 通知 Redis
            redis_client = get_redis_client()
            redis_client.publish("broadcast:notify", json.dumps({"source": "scheduler"}))

            # 标记提醒为已触发
            from core.providers.scheduler.reminder_store import ReminderStore
            store = ReminderStore()
            store.mark_fired(job_id)

            logger.bind(tag=TAG).info(f"提醒已触发: {job_id}, 消息: {message}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"触发提醒失败: {job_id}, {e}")

    def restore_jobs(self, reminders: list):
        """从 MySQL 恢复任务"""
        for r in reminders:
            if r["trigger_type"] == "date":
                run_date = datetime.fromisoformat(r["trigger_time"])
                if run_date > datetime.now():
                    self.add_once_job(r["id"], run_date, r["message"], r["device_id"])
            elif r["trigger_type"] == "cron":
                self.add_cron_job(r["id"], r["trigger_time"], r["message"], r["device_id"])
        logger.bind(tag=TAG).info(f"恢复 {len(reminders)} 个定时任务")

    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/scheduler/scheduler_manager.py
git commit -m "feat: implement SchedulerManager with APScheduler"
```

---

## Phase 3: Broadcast Agent

### Task 3.1: 实现 BroadcastManager

**Files:**
- Create: `main/xiaozhi-server/core/providers/broadcast/__init__.py`
- Create: `main/xiaozhi-server/core/providers/broadcast/broadcast_manager.py`
- Create: `main/xiaozhi-server/core/providers/broadcast/message_handler.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# main/xiaozhi-server/core/providers/broadcast/__init__.py
from .broadcast_manager import BroadcastManager

__all__ = ["BroadcastManager"]
```

- [ ] **Step 2: 创建 broadcast_manager.py**

```python
# main/xiaozhi-server/core/providers/broadcast/broadcast_manager.py
"""订阅 Redis 通知，从 MySQL 读取消息，调度 TTS 推送"""
import json
import threading
from datetime import datetime
from core.utils.db_manager import execute_query, execute_update, get_redis_client
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class BroadcastManager:
    def __init__(self, conn=None):
        self.conn = conn
        self._stop_event = threading.Event()
        self._thread = None
        logger.bind(tag=TAG).info("BroadcastManager 初始化")

    def start(self):
        """启动 Redis 订阅监听"""
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        logger.bind(tag=TAG).info("BroadcastManager 已启动监听")

    def stop(self):
        """停止监听"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _listen(self):
        """监听 Redis 通知"""
        redis_client = get_redis_client()
        pubsub = redis_client.pubsub()
        pubsub.subscribe("broadcast:notify")

        logger.bind(tag=TAG).info("开始监听 broadcast:notify 频道")
        for message in pubsub.listen():
            if self._stop_event.is_set():
                break
            if message["type"] == "message":
                self._process_pending_messages()

    def _process_pending_messages(self):
        """处理 pending 消息"""
        sql = """
            SELECT * FROM broadcast_queue
            WHERE status = 'pending'
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'normal' THEN 2
                    WHEN 'low' THEN 3
                END,
                created_at
            LIMIT 10
        """
        messages = execute_query(sql)
        for msg in messages:
            success = self._deliver_message(msg)
            if success:
                execute_update(
                    "UPDATE broadcast_queue SET status = 'delivered', delivered_at = %s WHERE id = %s",
                    (datetime.now(), msg["id"]),
                )
            else:
                execute_update(
                    "UPDATE broadcast_queue SET retry_count = retry_count + 1 WHERE id = %s",
                    (msg["id"],),
                )

    def _deliver_message(self, msg: dict) -> bool:
        """推送消息到设备"""
        try:
            if self.conn and hasattr(self.conn, "tts"):
                # 调用 TTS 推送
                from core.providers.tts.dto.dto import TTSMessageDTO, ContentType, SentenceType
                tts_msg = TTSMessageDTO(
                    content_type=ContentType.TEXT,
                    sentence_type=SentenceType.FIRST,
                    content=msg["content"],
                )
                self.conn.tts.tts_text_queue.put(tts_msg)
                logger.bind(tag=TAG).info(f"推送消息: {msg['id']}, 内容: {msg['content'][:50]}")
                return True
            else:
                logger.bind(tag=TAG).warning(f"无连接，跳过消息: {msg['id']}")
                return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"推送失败: {msg['id']}, {e}")
            return False

    def enqueue(self, source: str, priority: str, content: str):
        """入队消息"""
        sql = """
            INSERT INTO broadcast_queue (source, priority, content, status, created_at)
            VALUES (%s, %s, %s, 'pending', %s)
        """
        execute_update(sql, (source, priority, content, datetime.now()))

        redis_client = get_redis_client()
        redis_client.publish("broadcast:notify", json.dumps({"source": source}))
        logger.bind(tag=TAG).info(f"消息入队: source={source}, priority={priority}")
```

- [ ] **Step 3: 创建 message_handler.py**

```python
# main/xiaozhi-server/core/providers/broadcast/message_handler.py
"""消息优先级处理和设备空闲检测"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MessageHandler:
    def __init__(self, conn):
        self.conn = conn

    def is_device_idle(self) -> bool:
        """检查设备是否空闲"""
        if self.conn is None:
            return True
        return not getattr(self.conn, "client_is_speaking", False)

    def should_deliver(self, priority: str) -> bool:
        """根据优先级判断是否应该推送"""
        if priority == "high":
            return True
        if priority == "normal":
            return self.is_device_idle()
        if priority == "low":
            return self.is_device_idle()
        return False
```

- [ ] **Step 4: Commit**

```bash
git add main/xiaozhi-server/core/providers/broadcast/
git commit -m "feat: implement BroadcastAgent with Redis subscription and MySQL queue"
```

---

## Phase 4: Agent Registry

### Task 4.1: 实现 AgentRegistry

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/__init__.py`
- Create: `main/xiaozhi-server/core/providers/agent_registry/registry.py`
- Create: `main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/__init__.py
from .registry import AgentRegistry
from .agent_proxy import AgentProxy

__all__ = ["AgentRegistry", "AgentProxy"]
```

- [ ] **Step 2: 创建 registry.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/registry.py
"""扫描 workspace/agents/ 目录，加载所有 agent config.yaml"""
import os
import yaml
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class AgentRegistry:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.agents = {}

    def scan_workspace(self):
        """扫描 workspace/agents/ 目录"""
        agents_dir = os.path.join(self.workspace_path, "agents")
        if not os.path.exists(agents_dir):
            logger.bind(tag=TAG).warning(f"agents 目录不存在: {agents_dir}")
            return

        for name in os.listdir(agents_dir):
            agent_dir = os.path.join(agents_dir, name)
            config_path = os.path.join(agent_dir, "config.yaml")
            if os.path.isdir(agent_dir) and os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    config["_dir"] = agent_dir
                    self.agents[name] = config
                    logger.bind(tag=TAG).info(f"加载 agent: {name}, backend: {config.get('backend')}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"加载 agent 失败: {name}, {e}")

        logger.bind(tag=TAG).info(f"共加载 {len(self.agents)} 个 agent")

    def get_agent(self, name: str) -> dict:
        """获取 agent 配置"""
        return self.agents.get(name)

    def get_all_agents(self) -> dict:
        """获取所有 agent"""
        return self.agents

    def get_agent_list(self) -> list:
        """获取 agent 列表（用于 prompt 注入）"""
        return [
            {"name": name, "description": config.get("description", ""), "backend": config.get("backend", "")}
            for name, config in self.agents.items()
            if config.get("enabled", True)
        ]
```

- [ ] **Step 3: 创建 agent_proxy.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py
"""统一的 agent 调用代理，根据 backend 类型路由到不同后端"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class AgentProxy:
    def __init__(self, registry, config: dict):
        self.registry = registry
        self.config = config

    async def dispatch(self, agent_name: str, task: str) -> str:
        """分发任务到指定 agent"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return f"Agent '{agent_name}' 不存在"

        backend = agent.get("backend", "local")
        logger.bind(tag=TAG).info(f"分发任务到 {agent_name}, backend: {backend}")

        if backend == "multica":
            return await self._dispatch_multica(agent, task)
        elif backend == "claude_code":
            return await self._dispatch_claude_code(agent, task)
        elif backend == "openclaw":
            return await self._dispatch_openclaw(agent, task)
        elif backend == "local":
            return await self._dispatch_local(agent, task)
        else:
            return f"未知 backend: {backend}"

    async def _dispatch_multica(self, agent: dict, task: str) -> str:
        """通过 Multica API 分发"""
        # TODO: 实现 Multica API 调用
        return f"[Multica] 任务已分发: {task}"

    async def _dispatch_claude_code(self, agent: dict, task: str) -> str:
        """通过 Claude Code MCP 分发"""
        # TODO: 实现 Claude Code MCP 调用
        return f"[Claude Code] 任务已分发: {task}"

    async def _dispatch_openclaw(self, agent: dict, task: str) -> str:
        """通过 OpenClaw HTTP API 分发"""
        # TODO: 实现 OpenClaw HTTP 调用
        return f"[OpenClaw] 任务已分发: {task}"

    async def _dispatch_local(self, agent: dict, task: str) -> str:
        """本地执行"""
        return f"[Local] 任务已执行: {task}"

    async def check_health(self, agent_name: str) -> dict:
        """检查 agent 健康状态"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return {"name": agent_name, "status": "not_found"}
        return {"name": agent_name, "status": "unknown", "backend": agent.get("backend")}

    async def check_all_health(self) -> list:
        """检查所有 agent 健康状态"""
        results = []
        for name in self.registry.get_all_agents():
            results.append(await self.check_health(name))
        return results
```

- [ ] **Step 4: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/
git commit -m "feat: implement AgentRegistry and AgentProxy"
```

---

## Phase 5: Function Call 插件

### Task 5.1: 实现提醒相关插件

**Files:**
- Create: `main/xiaozhi-server/plugins_func/functions/set_reminder.py`
- Create: `main/xiaozhi-server/plugins_func/functions/list_reminders.py`
- Create: `main/xiaozhi-server/plugins_func/functions/delete_reminder.py`

- [ ] **Step 1: 创建 set_reminder.py**

```python
# main/xiaozhi-server/plugins_func/functions/set_reminder.py
"""设置提醒插件"""
from datetime import datetime, timedelta
from plugins_func.register import register_function, ToolType, ActionResponse, Action

set_reminder_desc = {
    "type": "function",
    "function": {
        "name": "set_reminder",
        "description": "设置提醒。支持一次性提醒（指定时间）和周期性提醒（cron 表达式）。",
        "parameters": {
            "type": "object",
            "properties": {
                "time": {
                    "type": "string",
                    "description": "提醒时间。格式：'YYYY-MM-DD HH:MM'（一次性）、'HH:MM'（每天）、'+10m'（10分钟后）、'0 8 * * *'（cron）",
                },
                "message": {
                    "type": "string",
                    "description": "提醒内容",
                },
                "repeat": {
                    "type": "boolean",
                    "description": "是否重复，默认 false",
                },
            },
            "required": ["time", "message"],
        },
    },
}


@register_function("set_reminder", set_reminder_desc, ToolType.WAIT)
def set_reminder(time: str, message: str, repeat: bool = False):
    from core.providers.scheduler.scheduler_manager import SchedulerManager
    from core.providers.scheduler.reminder_store import ReminderStore
    import uuid

    store = ReminderStore()
    scheduler = SchedulerManager()
    job_id = str(uuid.uuid4())

    if time.startswith("+"):
        # 相对时间：+10m, +1h
        minutes = int(time.replace("+", "").replace("m", ""))
        run_date = datetime.now() + timedelta(minutes=minutes)
        trigger_type = "date"
        trigger_time = run_date.isoformat()
        store.save("default", trigger_type, trigger_time, message)
        scheduler.add_once_job(job_id, run_date, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，{minutes}分钟后提醒你：{message}", None)

    elif repeat:
        # cron 表达式
        trigger_type = "cron"
        store.save("default", trigger_type, time, message)
        scheduler.add_cron_job(job_id, time, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，已设置周期性提醒：{message}", None)

    else:
        # 指定时间
        run_date = datetime.fromisoformat(time)
        trigger_type = "date"
        store.save("default", trigger_type, time, message)
        scheduler.add_once_job(job_id, run_date, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，将在 {time} 提醒你：{message}", None)
```

- [ ] **Step 2: 创建 list_reminders.py**

```python
# main/xiaozhi-server/plugins_func/functions/list_reminders.py
"""查询提醒列表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

list_reminders_desc = {
    "type": "function",
    "function": {
        "name": "list_reminders",
        "description": "查看当前所有活跃的提醒列表",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("list_reminders", list_reminders_desc, ToolType.WAIT)
def list_reminders():
    from core.providers.scheduler.reminder_store import ReminderStore

    store = ReminderStore()
    reminders = store.get_active_reminders("default")

    if not reminders:
        return ActionResponse(Action.REQLLM, "当前没有活跃的提醒", None)

    lines = []
    for r in reminders:
        lines.append(f"- [{r['id'][:8]}] {r['trigger_time']} | {r['message']}")
    return ActionResponse(Action.REQLLM, "当前提醒列表：\n" + "\n".join(lines), None)
```

- [ ] **Step 3: 创建 delete_reminder.py**

```python
# main/xiaozhi-server/plugins_func/functions/delete_reminder.py
"""删除提醒插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

delete_reminder_desc = {
    "type": "function",
    "function": {
        "name": "delete_reminder",
        "description": "删除指定的提醒",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "提醒 ID（完整 ID 或前 8 位）",
                },
            },
            "required": ["reminder_id"],
        },
    },
}


@register_function("delete_reminder", delete_reminder_desc, ToolType.WAIT)
def delete_reminder(reminder_id: str):
    from core.providers.scheduler.reminder_store import ReminderStore
    from core.providers.scheduler.scheduler_manager import SchedulerManager

    store = ReminderStore()
    store.delete(reminder_id)

    scheduler = SchedulerManager()
    scheduler.remove_job(reminder_id)

    return ActionResponse(Action.REQLLM, f"已删除提醒 {reminder_id[:8]}", None)
```

- [ ] **Step 4: Commit**

```bash
git add main/xiaozhi-server/plugins_func/functions/set_reminder.py
git add main/xiaozhi-server/plugins_func/functions/list_reminders.py
git add main/xiaozhi-server/plugins_func/functions/delete_reminder.py
git commit -m "feat: add reminder plugin functions (set/list/delete)"
```

---

### Task 5.2: 实现 Agent 管理插件

**Files:**
- Create: `main/xiaozhi-server/plugins_func/functions/list_agents.py`
- Create: `main/xiaozhi-server/plugins_func/functions/query_agent_tasks.py`
- Create: `main/xiaozhi-server/plugins_func/functions/dispatch_to_agent.py`
- Create: `main/xiaozhi-server/plugins_func/functions/agent_health_check.py`

- [ ] **Step 1: 创建 list_agents.py**

```python
# main/xiaozhi-server/plugins_func/functions/list_agents.py
"""列出所有可用 Agent 插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

list_agents_desc = {
    "type": "function",
    "function": {
        "name": "list_agents",
        "description": "列出所有可用的 Agent",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("list_agents", list_agents_desc, ToolType.WAIT)
def list_agents():
    from core.providers.agent_registry.registry import AgentRegistry
    from config.config_loader import load_backends_config

    config = load_backends_config()
    workspace_path = config.get("workspace_path", "./workspace")
    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    agents = registry.get_agent_list()
    if not agents:
        return ActionResponse(Action.REQLLM, "当前没有可用的 Agent", None)

    lines = []
    for a in agents:
        lines.append(f"- {a['name']}: {a['description']} (backend: {a['backend']})")
    return ActionResponse(Action.REQLLM, "可用 Agent 列表：\n" + "\n".join(lines), None)
```

- [ ] **Step 2: 创建 query_agent_tasks.py**

```python
# main/xiaozhi-server/plugins_func/functions/query_agent_tasks.py
"""查询指定 agent 的任务状态插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

query_agent_tasks_desc = {
    "type": "function",
    "function": {
        "name": "query_agent_tasks",
        "description": "查询指定 Agent 的任务状态",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称",
                },
            },
            "required": ["agent_name"],
        },
    },
}


@register_function("query_agent_tasks", query_agent_tasks_desc, ToolType.WAIT)
def query_agent_tasks(agent_name: str):
    # TODO: 通过 Multica/Gitea API 查询任务
    return ActionResponse(Action.REQLLM, f"正在查询 {agent_name} 的任务状态...", None)
```

- [ ] **Step 3: 创建 dispatch_to_agent.py**

```python
# main/xiaozhi-server/plugins_func/functions/dispatch_to_agent.py
"""分发任务给指定 agent 插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

dispatch_to_agent_desc = {
    "type": "function",
    "function": {
        "name": "dispatch_to_agent",
        "description": "分发任务给指定的 Agent 执行",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称",
                },
                "task": {
                    "type": "string",
                    "description": "任务描述",
                },
            },
            "required": ["agent_name", "task"],
        },
    },
}


@register_function("dispatch_to_agent", dispatch_to_agent_desc, ToolType.WAIT)
def dispatch_to_agent(agent_name: str, task: str):
    # TODO: 通过 AgentProxy 分发任务
    return ActionResponse(Action.REQLLM, f"已将任务分发给 {agent_name}: {task}", None)
```

- [ ] **Step 4: 创建 agent_health_check.py**

```python
# main/xiaozhi-server/plugins_func/functions/agent_health_check.py
"""巡检所有 agent 健康状态插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

agent_health_check_desc = {
    "type": "function",
    "function": {
        "name": "agent_health_check",
        "description": "巡检所有 Agent 的健康状态",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("agent_health_check", agent_health_check_desc, ToolType.WAIT)
def agent_health_check():
    # TODO: 检查所有 agent 状态
    return ActionResponse(Action.REQLLM, "正在巡检所有 Agent 状态...", None)
```

- [ ] **Step 5: Commit**

```bash
git add main/xiaozhi-server/plugins_func/functions/list_agents.py
git add main/xiaozhi-server/plugins_func/functions/query_agent_tasks.py
git add main/xiaozhi-server/plugins_func/functions/dispatch_to_agent.py
git add main/xiaozhi-server/plugins_func/functions/agent_health_check.py
git commit -m "feat: add agent management plugin functions"
```

---

## Phase 6: 模块集成

### Task 6.1: 修改 connection.py 集成新模块

**Files:**
- Modify: `main/xiaozhi-server/core/connection.py`

- [ ] **Step 1: 在 ConnectionHandler.__init__ 中添加新模块引用**

在 `__init__` 方法中添加：

```python
# 新模块引用
self.scheduler_manager = None
self.broadcast_manager = None
self.agent_registry = None
self.agent_proxy = None
```

- [ ] **Step 2: 在 _initialize_components 中初始化新模块**

在 `_initialize_components` 方法末尾添加：

```python
# 初始化新模块
try:
    from config.config_loader import load_backends_config
    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")

    # Agent Registry
    from core.providers.agent_registry.registry import AgentRegistry
    from core.providers.agent_registry.agent_proxy import AgentProxy
    self.agent_registry = AgentRegistry(workspace_path)
    self.agent_registry.scan_workspace()
    self.agent_proxy = AgentProxy(self.agent_registry, backends_config)

    # Scheduler
    from core.providers.scheduler.scheduler_manager import SchedulerManager
    from core.providers.scheduler.reminder_store import ReminderStore
    self.scheduler_manager = SchedulerManager()
    reminder_store = ReminderStore()
    active_reminders = reminder_store.get_all_active()
    self.scheduler_manager.restore_jobs(active_reminders)

    # Broadcast
    from core.providers.broadcast.broadcast_manager import BroadcastManager
    self.broadcast_manager = BroadcastManager(self)
    self.broadcast_manager.start()

    self.logger.bind(tag=TAG).info("新模块初始化完成")
except Exception as e:
    self.logger.bind(tag=TAG).error(f"新模块初始化失败: {e}")
```

- [ ] **Step 3: Commit**

```bash
git add main/xiaozhi-server/core/connection.py
git commit -m "feat: integrate scheduler, broadcast, and agent registry modules"
```

---

### Task 6.2: 修改 prompt_manager.py 注入 Agent 列表

**Files:**
- Modify: `main/xiaozhi-server/core/utils/prompt_manager.py`

- [ ] **Step 1: 在 update_context_info 中注入 agent 列表**

在 `update_context_info` 方法中添加：

```python
# 注入 Agent 列表到 dynamic_context
try:
    from config.config_loader import load_backends_config
    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")

    from core.providers.agent_registry.registry import AgentRegistry
    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    agent_list = registry.get_agent_list()
    if agent_list:
        agent_info = "\n可用 Agent:\n"
        for a in agent_list:
            agent_info += f"- {a['name']}: {a['description']}\n"
        if isinstance(self.context_data, dict):
            self.context_data["agent_list"] = agent_info
        else:
            self.context_data = agent_info
except Exception as e:
    self.logger.bind(tag=TAG).debug(f"注入 Agent 列表失败: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/utils/prompt_manager.py
git commit -m "feat: inject agent list into prompt dynamic_context"
```

---

## Phase 7: Context Manager

### Task 7.1: 实现 ContextManager

**Files:**
- Create: `main/xiaozhi-server/core/providers/context_manager/__init__.py`
- Create: `main/xiaozhi-server/core/providers/context_manager/context_manager.py`
- Create: `main/xiaozhi-server/core/providers/context_manager/summarizer.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# main/xiaozhi-server/core/providers/context_manager/__init__.py
from .context_manager import ContextManager

__all__ = ["ContextManager"]
```

- [ ] **Step 2: 创建 context_manager.py**

```python
# main/xiaozhi-server/core/providers/context_manager/context_manager.py
"""监控 context 长度，触发压缩或滑动窗口"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ContextManager:
    def __init__(self, model_context_window: int = 200000):
        self.threshold = int(model_context_window * 0.5)
        self.max_window = int(model_context_window * 0.75)

    def check_and_compress(self, messages: list, llm=None) -> list:
        """检查并压缩上下文"""
        total_tokens = self._estimate_tokens(messages)
        if total_tokens < self.threshold:
            return messages

        logger.bind(tag=TAG).info(f"上下文接近阈值: {total_tokens}/{self.threshold}, 开始压缩")

        # 阶段一：滑动窗口
        windowed = self._sliding_window_with_memory(messages)
        if self._estimate_tokens(windowed) < self.max_window:
            return windowed

        # 阶段二：LLM 摘要压缩
        if llm:
            from .summarizer import Summarizer
            summarizer = Summarizer(llm)
            old_messages = windowed[:-10]
            recent_messages = windowed[-10:]
            summary = summarizer.compress(old_messages)
            return [{"role": "system", "content": f"历史摘要: {summary}"}] + recent_messages

        return windowed

    def _sliding_window_with_memory(self, messages: list, keep_count: int = 20) -> list:
        """滑动窗口：保留最近 N 轮"""
        if len(messages) <= keep_count:
            return messages
        return messages[-keep_count:]

    def _estimate_tokens(self, messages: list) -> int:
        """粗略估算 token 数"""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return int(total_chars * 1.5)
```

- [ ] **Step 3: 创建 summarizer.py**

```python
# main/xiaozhi-server/core/providers/context_manager/summarizer.py
"""调用 LLM 压缩对话历史为摘要"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class Summarizer:
    def __init__(self, llm):
        self.llm = llm

    def compress(self, messages: list) -> str:
        """压缩消息为摘要"""
        conversation = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages
        )
        prompt = f"请将以下对话压缩为简洁的摘要，保留关键信息（任务、决策、时间点）：\n\n{conversation}"
        try:
            summary = self.llm.response_no_stream(system_prompt=prompt, user_prompt="生成摘要")
            logger.bind(tag=TAG).info(f"摘要压缩完成，原 {len(messages)} 条消息")
            return summary
        except Exception as e:
            logger.bind(tag=TAG).error(f"摘要压缩失败: {e}")
            return f"[压缩失败: {len(messages)} 条消息]"
```

- [ ] **Step 4: Commit**

```bash
git add main/xiaozhi-server/core/providers/context_manager/
git commit -m "feat: implement ContextManager with sliding window and LLM summarization"
```

---

## 依赖安装

在 `requirements.txt` 中添加：

```
apscheduler>=3.10.0
pymysql>=1.1.0
redis>=5.0.0
pyyaml>=6.0
```

运行：`pip install apscheduler pymysql redis pyyaml`

---

## 验证清单

- [ ] workspace 目录结构创建完成
- [ ] MySQL `xiaozhi_agent` 数据库和 3 张表创建完成
- [ ] Redis db3 连接正常
- [ ] backends.yaml 配置加载正常
- [ ] SchedulerManager 能添加/删除/恢复定时任务
- [ ] BroadcastManager 能订阅 Redis 通知并处理消息
- [ ] AgentRegistry 能扫描 workspace 并加载 agent 列表
- [ ] 7 个 plugin function 能正常注册和调用
- [ ] ContextManager 能检测上下文长度并触发压缩
- [ ] connection.py 能正常初始化所有新模块
