# CEO Agent 智能助手设计文档

> 日期: 2026-06-08
> 状态: Draft

## 1. 概述

将 ESP32 设备升级为个人智能助手，通过 CEO Agent 架构实现：
- 语音设置/管理日程提醒（主动播报）
- 作息调整（默认时间表 + 语音微调）
- 对接 Multica / Claude Code / OpenClaw 上的已有 Agent
- 语音查询任务状态、分发任务给多 Agent
- 主动巡检 Agent 健康状态，异常时语音通知

## 2. 架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                       xiaozhi-server                          │
│                                                               │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │ WebSocket │◄──│  Scheduler   │───►│  Broadcast Agent    │ │
│  │ Connection│    │ (APScheduler)│    │  (TTS播报 + 消息路由) │ │
│  └──────────┘    └──────┬───────┘    └──────────┬──────────┘ │
│       ▲                 │                        │            │
│       │           ┌─────┴──────┐                 │            │
│       │           │ MySQL+Redis│                 │            │
│       │           └────────────┘                 │            │
│       │                                          │            │
│  ┌────┴─────┐    ┌──────────────────┐           │            │
│  │  ASR     │    │  Agent Registry  │           │            │
│  └──────────┘    └────────┬─────────┘           │            │
│                           │                      │            │
└───────────────────────────┼──────────────────────┼────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   CEO Agent     │  最高决策者
                   │  (Claude Code)  │
                   └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │  Multica 直管 │ │ Claude PM│ │  OpenClaw    │
     │              │ │(项目管理) │ │  (个人助理)   │
     │ Multica agent│ │          │ │              │
     │ 执行 + 看板   │ │ 子代理执行│ │ 网上找资料    │
     │              │ │ 双写看板  │ │ GitHub 对比   │
     └──────────────┘ │ Gitea    │ │ 三层记忆      │
                      │ Multica  │ └──────────────┘
                      └──────────┘
```

### 2.2 CEO Agent 定位

CEO Agent 是一个**独立的 Claude Code agent**，拥有自己的 workspace、memory 和 skills。它不复用 xiaozhi-server 的 LLM provider，而是作为独立的决策中心运行。

角色分工：

- **ESP32** = 纯语音接口（麦克风 + 喇叭）
- **Broadcast Agent** = 专职播报 agent，从其他 agent 收集消息，调用 TTS 推送到 ESP32
- **CEO Agent** = Claude Code agent，最高决策者，决定任务由谁管理
- **Claude PM** = 项目级 Claude Code agent，管理具体项目，用 Claude 子代理执行
- **Multica** = 看板 + 直管执行引擎，按**项目 (project)** 建 issue，agent 编排、任务派发（http://192.168.31.179:18080）
- **Gitea Issues** = 按**仓库 (repo)** 建 issue（http://192.168.31.179:8418），Claude PM 管理时使用
- **OpenClaw Agent** = 个人助理，网上找资料、GitHub 信息对比筛选，带 OpenViking 三层记忆

两种管理模式：

**模式一：Multica 直管**（CEO 直接派发到 Multica）
```
CEO 创建 issue → Multica 分配 agent → Multica agent (Claude Code runtime) 执行 → 完成
```
Multica 负责执行 + 看板，Gitea 不涉及。

**模式二：Claude PM 管理**（项目级管理，Claude 子代理执行）
```
CEO 委派给 Claude PM
  → Claude PM 同时写 Gitea + Multica issue（纯记录，不派发）
  → Claude PM 启动 Claude 子代理执行任务
  → 完成后 Claude PM 更新两边状态 → 语音播报
```
Gitea + Multica 做看板追踪，Claude 子代理做实际执行。

**OpenClaw 助理模式**：
```
你需要调研 → CEO 委派给 OpenClaw Agent
  → OpenClaw 网上找资料、GitHub 信息对比筛选
  → 结果返回 CEO → 语音播报
  → OpenClaw 用 OpenViking 记忆积累调研经验
```

数据流：

```
语音输入: ESP32 -> ASR -> 文字 -> CEO Agent (Claude Code) -> 决策
  ├── 简单任务 → Multica 直管（Multica agent 执行）
  ├── 项目级任务 → Claude PM 管理（Claude 子代理执行，双写看板）
  └── 调研/信息收集 → OpenClaw 助理（网上找资料、GitHub 对比）
语音输出: CEO/Claude PM/OpenClaw 输出 -> Broadcast Agent -> TTS -> ESP32
主动播报: Scheduler -> Broadcast Agent -> TTS -> ESP32
```

### 2.3 会话模型与上下文管理

**会话模型**：
- 设备保持 WebSocket 长连接，会话持续
- 调度器推送复用已有连接，不创建新会话
- Memory / Tools / Config 跨推送保持一致
- 设备断线重连后自动加载持久化的 memory

**上下文管理（混合策略）**：

当会话上下文接近模型 context window 的一半时，采用两阶段处理（先低成本后高成本）：

1. **阶段一：滑动窗口 + Memory**（零成本，优先尝试）
   - 保留最近 N 轮对话
   - 更早的对话存入 agent 的 memory 文件
   - 需要时从 memory 检索相关上下文

2. **阶段二：自动摘要压缩**（消耗 LLM tokens，阶段一不够时使用）
   - 用 LLM 将较早的对话压缩成摘要
   - 保留关键信息（任务、决策、时间点）
   - 释放 token 空间，对话连续性不受影响

触发阈值：`context_tokens > model_context_window * 0.5`

### 2.4 各 Agent 记忆策略

每个 agent 类型使用不同的记忆系统：

| Agent 类型 | 记忆系统 | 说明 |
|-----------|----------|------|
| **CEO Agent** (Claude Code) | claude-mem | 跨会话持久化记忆数据库，MCP server 提供语义搜索 |
| **Multica agents** | xiaozhi-server 层兜底 | Multica 无内置记忆，由 xiaozhi-server 的 MySQL 表存储对话历史 |
| **OpenClaw agents** | OpenViking 三层记忆 | 自带完整的记忆系统（日记 + 长期记忆 + 向量记忆） |

**Multica 记忆兜底方案**（`xiaozhi_agent.agent_memory` 表）：

```sql
CREATE TABLE agent_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,         -- 'user' / 'agent'
    content TEXT NOT NULL,
    summary TEXT,                      -- 压缩后的摘要（旧记录）
    created_at DATETIME NOT NULL,
    INDEX idx_agent_time (agent_name, created_at)
);
```

调用 Multica agent 前，从该表读取历史摘要注入上下文；调用后将本次交互存入。超过 N 轮后自动压缩成摘要。

**OpenClaw 三层记忆架构**：

```
┌─────────────────────────────────────────┐
│         Layer 3: OpenViking             │
│  向量数据库，语义记忆，自动抽取            │
│  技术栈: LanceDB + BAAI/bge-m3 (1024维)  │
│  API: memory_store / memory_recall       │
├─────────────────────────────────────────┤
│         Layer 2: MEMORY.md              │
│  长期记忆，人工维护，核心规则              │
│  路径: workspace/MEMORY.md               │
├─────────────────────────────────────────┤
│         Layer 1: memory/*.md            │
│  日记，每日流水账，自动归档                │
│  路径: workspace/memory/YYYY-MM-DD.md    │
└─────────────────────────────────────────┘
```

- **Layer 1 日记层**：每天自动创建 `YYYY-MM-DD.md`，记录原始对话和事件
- **Layer 2 长期记忆**：`MEMORY.md`，人工从日记中提炼核心规则、偏好、决策
- **Layer 3 向量记忆**：OpenViking 自动抽取语义记忆，通过 `memory_recall` 语义检索

记忆流转：用户对话 → Layer 3 自动抽取 → 重要事件写入 Layer 1 → 定期整理到 Layer 2

## 3. Agent Workspace 目录结构

采用文件系统驱动的 Agent 组织方式，每个 Agent 拥有独立的 workspace：

```
workspace/                           # 公司根目录
├── ceo/                             # CEO Agent（Claude Code，记忆: claude-mem）
│   ├── config.yaml                  # CEO 的配置
│   ├── skills/                      # CEO 的技能
│   │   ├── delegate_task.py         # 委派任务
│   │   ├── schedule_reminder.py     # 调度提醒
│   │   ├── health_check.py          # 健康巡检
│   │   └── sync_to_gitea.py         # Gitea 同步
│   └── logs/                        # 对话日志
│
├── pm/                              # Claude PM（项目管理，记忆: claude-mem）
│   ├── config.yaml                  # PM 的配置
│   ├── skills/
│   │   ├── create_issue.py          # 创建 issue（双写 Gitea + Multica）
│   │   ├── update_status.py         # 更新状态（双写）
│   │   └── report_progress.py       # 进度汇报
│   └── logs/
│
├── broadcast/                       # Broadcast Agent（专职 TTS 播报）
│   └── config.yaml                  # 播报配置
│
├── agents/                          # 下属 Agent 们（Multica 管理）
│   ├── executor/                    # 执行 agent
│   │   ├── config.yaml
│   │   ├── skills/
│   │   └── logs/
│   ├── reviewer/                    # 审查 agent（Multica, Claude Code runtime）
│   │   ├── config.yaml
│   │   ├── skills/
│   │   └── logs/
│   └── assistant/                   # OpenClaw 个人助理（记忆: OpenViking 三层记忆）
│       ├── config.yaml              # backend: openclaw, 职责: 调研/信息收集/GitHub对比
│       ├── MEMORY.md                # Layer 2: 长期记忆
│       ├── memory/                  # Layer 1: 日记
│       │   └── YYYY-MM-DD.md
│       ├── skills/
│       │   ├── web_research.py      # 网上找资料
│       │   └── github_compare.py    # GitHub 信息对比筛选
│       └── logs/
│
├── backends.yaml                    # 后端连接配置（含 MySQL/Redis 配置）
```

### 3.1 Agent config.yaml 格式

```yaml
name: 项目管理
description: 擅长项目进度跟踪、任务分配
backend: multica                    # multica / claude_code / openclaw / local
backend_id: agent-123               # 后端系统中的 agent ID
model: openai/gpt-4o                # 可选：指定使用的模型
enabled: true
```

### 3.2 backends.yaml 格式

```yaml
workspace_path: ./workspace           # workspace 根目录，可配置

# 数据库配置
mysql:
  host: localhost
  port: 3306
  database: xiaozhi_agent
  user: root
  password: xxx

redis:
  host: localhost
  port: 6379
  db: 3
  password: null

# 任务看板
gitea:
  url: http://192.168.31.179:8418
  repo: ""                            # 用户指定的 Gitea 仓库，issue 按仓库创建
  token: xxx                          # Gitea API token

# 后端 Agent 服务
multica:
  url: http://192.168.31.179:18080
  api_key: xxx
  project: ""                         # 用户指定的 Multica 项目，issue 按项目创建

claude_code:
  type: mcp
  command: claude
  args: ["mcp", "serve"]

openclaw:
  type: http                          # OpenClaw 通过 HTTP REST API 对接
  url: http://192.168.31.179:18789
  workspace: /home/dapao/.openclaw
  role: assistant                     # 个人助理：网上找资料、GitHub 信息对比筛选
```

**OpenClaw 集成说明**: OpenClaw 提供 HTTP REST API，通过 `AgentProxy` 将工具调用转换为 HTTP 请求。OpenClaw 作为个人助理，负责调研、信息收集、GitHub 对比筛选等任务，使用 OpenViking 三层记忆积累经验。同时集成到 Multica 中，可在 Multica 看板上追踪其任务状态。

## 4. 启动流程

```
xiaozhi-server 启动
  1. 加载 backends.yaml -> 获取 workspace_path 和后端配置
  2. 连接 MySQL (xiaozhi_agent 数据库) 和 Redis (db3)
  3. AgentRegistry.scan_workspace(workspace_path/agents/)
     -> 遍历 */config.yaml -> 构建 agent 列表
  4. CEO Agent 初始化
     -> 启动 Claude Code agent (workspace/ceo/)
     -> 加载 CEO 的 memory、skills、config
  5. Broadcast Agent 初始化
     -> 订阅 Redis channel "broadcast:notify"
     -> 启动消息监听协程
  6. SchedulerManager.__init__()
     -> 从 MySQL 加载未触发的提醒
     -> 恢复 APScheduler 任务
     -> 注册定时任务回调 -> MySQL INSERT + Redis PUBLISH
  7. Server MCP 初始化
     -> 从 data/.mcp_server_settings.json 加载 MCP 服务
     -> 连接 Multica / Claude Code MCP 服务
  8. ContextManager 初始化
     -> 设置 context window 阈值 (model_context_window * 0.5)
  9. WebSocket 等待设备连接
```

## 5. 模块设计

### 5.1 Scheduler 模块

**位置**: `main/xiaozhi-server/core/providers/scheduler/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块入口 |
| `scheduler_manager.py` | 管理 APScheduler 的 BackgroundScheduler，添加/删除/查询定时任务 |
| `reminder_store.py` | MySQL 持久化提醒任务 |

**存储**: MySQL（新建 `xiaozhi_agent` 数据库）+ Redis db3（缓存和 Pub/Sub）

**任务类型**:

| 类型 | 触发方式 | 示例 |
|------|----------|------|
| 一次性提醒 | `date` trigger (指定时间点) | `2026-06-08 14:00 提醒开会` |
| 周期性提醒 | `cron` trigger (cron 表达式) | `每天 08:00 播报今日任务` |
| 语音设置 | 解析相对时间转 date trigger | `10分钟后提醒我喝水` |

**MySQL Schema** (`xiaozhi_agent` 数据库):

```sql
CREATE TABLE reminders (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    trigger_type VARCHAR(16) NOT NULL,     -- 'date' / 'cron'
    trigger_time VARCHAR(64),              -- ISO 时间或 cron 表达式
    message TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'active',   -- 'active' / 'fired' / 'deleted'
    created_at DATETIME NOT NULL,
    fired_at DATETIME,
    INDEX idx_device_status (device_id, status)
);

CREATE TABLE broadcast_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(32) NOT NULL,           -- 'ceo' / 'scheduler' / 'pm' / 'openclaw'
    priority VARCHAR(16) NOT NULL,         -- 'high' / 'normal' / 'low'
    content TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',  -- 'pending' / 'delivered' / 'failed'
    retry_count INT DEFAULT 0,
    created_at DATETIME NOT NULL,
    delivered_at DATETIME,
    INDEX idx_status_priority (status, priority)
);

CREATE TABLE agent_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,             -- 'user' / 'agent'
    content TEXT NOT NULL,
    summary TEXT,                          -- 压缩后的摘要（旧记录）
    created_at DATETIME NOT NULL,
    INDEX idx_agent_time (agent_name, created_at)
);
```

**消息队列设计（MySQL 持久化 + Redis 实时通知）**:

生产者（CEO/Claude PM/Scheduler/OpenClaw）：
1. 写入 MySQL `broadcast_queue` 表（持久化）
2. 发布通知到 Redis channel `broadcast:notify`（实时触发，不含消息体）

消费者（Broadcast Agent）：
1. 订阅 Redis channel `broadcast:notify`（收到信号）
2. 从 MySQL 读取 pending 消息（按优先级排序）
3. 处理成功 → 更新 MySQL 状态为 `delivered`
4. 处理失败 → 状态保持 `pending`，下次通知时重试

```
调度器到期
  -> MySQL INSERT INTO broadcast_queue (source='scheduler', content='该喝水了')
  -> Redis PUBLISH broadcast:notify '{"id": 123}'
  -> Broadcast Agent 收到通知 -> MySQL SELECT pending 消息 -> TTS 推送
  -> 成功 -> MySQL UPDATE status='delivered'
  -> 失败 -> retry_count++, 保持 pending
```

### 5.2 Agent Registry

**位置**: `main/xiaozhi-server/core/providers/agent_registry/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块入口 |
| `registry.py` | 扫描 workspace/agents/ 目录，加载所有 agent config.yaml |
| `agent_proxy.py` | 统一的 agent 调用代理，根据 backend 类型路由到不同后端 |

**动态加载流程**:

```
服务启动 -> Registry.scan_workspace()
  -> 遍历 workspace/agents/*/config.yaml
  -> 构建 agent 列表 [{name, description, backend, backend_id}]
  -> 注入到 PromptManager 的 dynamic_context
```

**后端路由**:

| backend | 调用方式 |
|---------|----------|
| `multica` | 通过 Server MCP (SSE) 调用 Multica API |
| `claude_code` | 通过 Server MCP (stdio) 调用 Claude Code |
| `openclaw` | 通过 HTTP API 调用 OpenClaw |
| `local` | 直接在 xiaozhi-server 内执行 |

### 5.3 新增 Function Call 工具

通过 `plugins_func` 注册以下工具：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `set_reminder` | 设置提醒 | `time` (时间/cron), `message` (提醒内容), `repeat` (是否重复) |
| `list_reminders` | 查看当前提醒列表 | 无 |
| `delete_reminder` | 删除指定提醒 | `reminder_id` |
| `list_agents` | 列出所有可用 Agent | 无 |
| `query_agent_tasks` | 查询指定 agent 的任务状态 | `agent_name` |
| `dispatch_to_agent` | 分发任务给指定 agent | `agent_name`, `task` |
| `agent_health_check` | 巡检所有 agent 健康状态 | 无 |

### 5.4 Broadcast Agent

**位置**: `main/xiaozhi-server/core/providers/broadcast/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块入口 |
| `broadcast_manager.py` | 订阅 Redis 通知，从 MySQL 读取消息，调度 TTS 推送 |
| `message_handler.py` | 消息优先级处理和设备空闲检测 |

**模式**: MySQL 持久化 + Redis 实时通知

**职责**：
- 订阅 Redis channel `broadcast:notify`，接收通知信号
- 从 MySQL `broadcast_queue` 表读取 pending 消息（按优先级排序）
- 根据优先级处理：high=立即播报，normal=排队等空闲，low=空闲时播报
- 检查设备空闲状态（`conn.client_is_speaking`）
- 调用 TTS 生成音频
- 通过 WebSocket 推送到 ESP32
- 播报成功 → 更新 MySQL 状态为 `delivered`
- 播报失败 → `retry_count++`，保持 `pending`，下次重试

**消息流转**:
```
生产者 → MySQL INSERT broadcast_queue → Redis PUBLISH broadcast:notify
消费者 → Redis SUBSCRIBE broadcast:notify → MySQL SELECT pending → TTS 推送
成功 → MySQL UPDATE status=delivered
失败 → MySQL UPDATE retry_count++，保持 pending
```

**优先级处理**：
- `high`: 立即播报（打断当前对话）
- `normal`: 排队等空闲
- `low`: 空闲时播报，有新消息时可被覆盖

### 5.5 Context Manager（上下文管理）

**位置**: `main/xiaozhi-server/core/providers/context_manager/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块入口 |
| `context_manager.py` | 监控 context 长度，触发压缩或滑动窗口 |
| `summarizer.py` | 调用 LLM 压缩对话历史为摘要 |

**混合策略实现（先低成本后高成本）**：

```python
class ContextManager:
    def __init__(self, model_context_window: int):
        self.threshold = model_context_window * 0.5
        self.max_window = model_context_window * 0.75

    def check_and_compress(self, messages: list) -> list:
        total_tokens = self._count_tokens(messages)
        if total_tokens < self.threshold:
            return messages  # 无需处理

        # 阶段一：滑动窗口 + Memory（零成本，优先尝试）
        windowed = self._sliding_window_with_memory(messages)
        if self._count_tokens(windowed) < self.max_window:
            return windowed

        # 阶段二：自动摘要压缩（消耗 LLM tokens）
        old_messages = windowed[:-10]
        recent_messages = windowed[-10:]
        summary = self.summarizer.compress(old_messages)
        return [{"role": "system", "content": f"历史摘要: {summary}"}] + recent_messages

    def _sliding_window_with_memory(self, messages: list) -> list:
        # 保留最近 N 轮，更早的存入 memory
        keep_count = 20
        to_store = messages[:-keep_count]
        self._save_to_memory(to_store)
        return messages[-keep_count:]
```

### 5.6 CEO Agent (Claude Code)

CEO Agent 作为独立的 Claude Code agent 运行，拥有完整的 workspace：

**workspace/ceo/config.yaml**:
```yaml
name: CEO
description: 私人助手，决策中心
backend: claude_code
model: claude-opus-4-7
prompt_template: ceo-prompt.txt
context_window: 200000              # Claude 的 context window
compression_threshold: 0.5          # 触发压缩的阈值
schedule:
  morning_briefing: "08:00"
  evening_summary: "22:00"
  health_check_interval: 3600
```

**CEO 的 skills/**:
- `delegate_task.py`: 委派任务给下属 agent
- `schedule_reminder.py`: 创建/管理提醒
- `health_check.py`: 巡检下属 agent 状态
- `context_compress.py`: 触发上下文压缩
- `sync_to_gitea.py`: 同步任务状态到 Gitea Issues

**CEO 与 xiaozhi-server 的交互**：
- xiaozhi-server 通过 MCP stdio 连接 CEO Agent
- CEO Agent 暴露 tools: `delegate`, `remind`, `check_health`, `broadcast`, `sync_task`
- xiaozhi-server 将用户语音转文字后调用 CEO 的 tools

### 5.7 后端 MCP 集成

利用已有的 Server MCP 机制 (`data/.mcp_server_settings.json`) 接入外部服务。

**Multica 集成**:

```json
{
  "mcpServers": {
    "multica": {
      "url": "http://192.168.31.179:18080/mcp/sse",
      "env": {
        "MULTICA_API_KEY": "xxx"
      }
    }
  }
}
```

**Claude Code 集成 (CEO Agent)**:

```json
{
  "mcpServers": {
    "ceo_agent": {
      "command": "claude",
      "args": ["mcp", "serve"],
      "env": {
        "CLAUDE_WORKSPACE": "./workspace/ceo"
      }
    }
  }
}
```

## 6. 数据流

### 6.1 语音设置提醒

```
你: "10分钟后提醒我喝水"
ESP32 -> ASR -> 文字 -> CEO Agent (Claude Code)
  -> CEO 调用 set_reminder tool
  -> SchedulerManager.add_job(trigger="date", run_date=now+10m)
  -> ReminderStore.save(reminder)
  -> CEO 回复: "好的，10分钟后提醒你喝水"
  -> Broadcast Agent -> TTS -> ESP32

... 10分钟后 ...

SchedulerManager 触发
  -> Broadcast Agent 队列 (priority: normal)
  -> 等待设备空闲
  -> TTS("该喝水了") -> WebSocket 推送 -> ESP32 播报
```

### 6.2 查询任务状态

```
你: "项目管理在忙什么"
ESP32 -> ASR -> CEO Agent
  -> CEO 查询 Multica API (agent 任务列表)
  -> 返回进行中的任务 -> CEO 总结
  -> Broadcast Agent -> TTS -> ESP32
```

### 6.3 Multica 直管模式

```
你: "帮我修复登录 bug"
ESP32 -> ASR -> CEO Agent
  -> CEO 判断: 简单任务，Multica 直管
  -> Multica API 在配置的项目中创建 issue + 分配 executor agent
  -> Multica agent (Claude Code runtime) 执行
  -> 完成 -> CEO 更新 Multica 项目中的 issue 状态
  -> Broadcast Agent -> TTS -> ESP32
```

### 6.4 Claude PM 管理模式（Claude 子代理执行 + 双写看板）

```
你: "重构整个认证模块"
ESP32 -> ASR -> CEO Agent
  -> CEO 判断: 项目级任务，委派给 Claude PM
  -> Claude PM 同时:
     ├── Gitea API 在配置的仓库中创建 issue "重构认证模块" (label: 进行中)
     └── Multica API 在配置的项目中创建 issue (纯记录，不派发)
  -> Claude PM 启动 Claude 子代理执行
  -> 完成后 Claude PM 更新两边状态:
     ├── Gitea issue (label: 已完成, 评论附结果)
     └── Multica issue (状态: 已完成)
  -> Broadcast Agent -> TTS -> ESP32
```

### 6.5 OpenClaw 助理模式（调研/信息收集）

```
你: "帮我调研下市面上的 IoT 平台，对比优劣"
ESP32 -> ASR -> CEO Agent
  -> CEO 判断: 调研任务，委派给 OpenClaw Agent
  -> OpenClaw:
     ├── 网上搜索 IoT 平台信息
     ├── GitHub 上对比各平台 star、issue、活跃度
     └── 整理对比报告
  -> 结果返回 CEO -> 语音播报
  -> OpenClaw 用 OpenViking 存储调研经验
```

### 6.6 主动巡检

```
[Cron: 每小时] -> SchedulerManager 触发
  -> CEO Agent 调用 check_health
  -> 查询所有 Agent 状态 (Multica + CC + OpenClaw)
  -> 发现异常? -> Broadcast Agent (priority: high) -> TTS("代码审查 agent 已离线30分钟")
  -> 一切正常? -> 静默，不打扰
```

## 7. 实现计划

### Phase 1: 基础框架
- [ ] 创建 workspace 目录结构 (ceo/, broadcast/, agents/)
- [ ] 实现 backends.yaml 配置加载（含 MySQL/Redis 连接配置）
- [ ] 新建 MySQL `xiaozhi_agent` 数据库和 `reminders` 表
- [ ] 连接 Redis db3

### Phase 2: CEO Agent + Claude PM (Claude Code)
- [ ] 创建 CEO Agent 的 workspace (ceo/config.yaml, skills/)
- [ ] 创建 Claude PM 的 workspace (pm/config.yaml, skills/)
- [ ] 实现 CEO Agent 的 MCP server (暴露 delegate, remind, check_health, broadcast tools)
- [ ] 实现 Claude PM 的 MCP server (暴露 create_issue, update_status, report_progress tools)
- [ ] 实现 Claude PM 的子代理执行逻辑（Claude 子代理执行，不派发到 Multica）
- [ ] 通过 Server MCP 将 CEO Agent 和 Claude PM 接入 xiaozhi-server

### Phase 3: Broadcast Agent
- [ ] 实现 BroadcastManager (订阅 Redis channel "broadcast:notify")
- [ ] 实现优先级处理 (high/normal/low)
- [ ] 实现空闲等待机制
- [ ] 播报完成更新 MySQL `broadcast_queue` 状态

### Phase 4: Scheduler 模块
- [ ] 实现 SchedulerManager (APScheduler 封装)
- [ ] 实现 ReminderStore (MySQL 持久化)
- [ ] 定时任务回调 -> MySQL INSERT broadcast_queue + Redis PUBLISH broadcast:notify

### Phase 5: Context Manager
- [ ] 实现 ContextManager (监控 context 长度)
- [ ] 实现 Summarizer (LLM 压缩对话历史)
- [ ] 实现滑动窗口 + Memory 策略

### Phase 6: 后端集成
- [ ] 配置 Multica MCP 连接（看板 + 直管执行）
- [ ] 配置 Claude Code MCP 连接 (CEO Agent + Claude PM)
- [ ] 实现 OpenClaw HTTP API 对接（个人助理：调研、GitHub 对比）
- [ ] 实现 Gitea API 对接 (sync_to_gitea.py — Claude PM 双写看板)

### Phase 7: 作息调整
- [ ] 实现默认日程时间表（可配置）
- [ ] 支持语音修改作息时间
- [ ] 早晚自动播报（今日任务 / 今日总结）

## 8. 配置示例

### 8.1 workspace/ceo/config.yaml (CEO Agent - Claude Code)

```yaml
name: CEO
description: 私人助手，决策中心
backend: claude_code
model: claude-opus-4-7
context_window: 200000
compression_threshold: 0.5
enabled: true
schedule:
  morning_briefing: "08:00"      # 早间播报
  evening_summary: "22:00"       # 晚间总结
  health_check_interval: 3600    # 巡检间隔（秒）
```

### 8.2 workspace/broadcast/config.yaml (Broadcast Agent)

```yaml
name: Broadcast
description: 专职 TTS 播报
backend: local
enabled: true
redis_channel: "broadcast:notify"
redis_db: 3
priority_levels:
  high: immediate                 # 立即播报
  normal: queue                   # 排队等空闲
  low: idle                       # 空闲时播报
```

### 8.3 workspace/pm/config.yaml (Claude PM - 项目管理)

```yaml
name: Claude-PM
description: 项目级管理，Claude 子代理执行，双写 Gitea + Multica 看板
backend: claude_code
model: claude-sonnet-4-6
enabled: true
```

### 8.4 workspace/agents/*/config.yaml (下属 Agent)

```yaml
name: 项目管理
description: 擅长项目进度跟踪、任务分配
backend: multica
backend_id: agent-123
model: null                      # 使用后端默认模型
enabled: true
```

## 9. 依赖

- `apscheduler` - 定时任务调度
- `pyyaml` - YAML 配置解析
- `mysql-connector-python` 或 `pymysql` - MySQL 连接（提醒持久化）
- `redis` - Redis 连接（实时通知 + 缓存）
- `mcp` - 已有依赖，MCP 客户端连接

**已有服务**：
- MySQL: 已有服务，新建 `xiaozhi_agent` 数据库
- Redis: 已有服务，使用 db3
- Gitea: 已有服务，http://192.168.31.179:8418
- Multica: 已有服务，http://192.168.31.179:18080
- OpenClaw: 已有服务，http://192.168.31.179:18789
- Claude Code: 本地安装，用于 CEO Agent 和 Claude PM

## 10. 约束和边界

- 当前设计面向单设备（一个 ESP32），多设备支持需要后续扩展
- 设备断线期间的提醒会丢失（后续可通过 MQTT 遗嘱消息改进）
- 后端 Agent 的可用性依赖各自服务的稳定性（Multica、OpenClaw、Claude Code）
- 语音播报排队机制在同一会话内生效，断线重连后排队丢失
- MySQL 和 Redis 服务需要在部署前准备好，数据库 `xiaozhi_agent` 需要预先创建
- Gitea 需要在 `backends.yaml` 中配置用于任务追踪的仓库，issue 按仓库创建
- Multica 需要在 `backends.yaml` 中配置项目名称，issue 按项目创建
- Claude PM 双写模式会增加 API 调用开销（Gitea 仓库 + Multica 项目各一次）
- Multica 的 agent 需要预先在 Multica 上创建并配置好 instructions 和 skills
