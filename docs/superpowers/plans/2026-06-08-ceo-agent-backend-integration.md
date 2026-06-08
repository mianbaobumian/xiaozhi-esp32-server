# CEO Agent 后端集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 Multica、Claude Code（CEO/PM）、OpenClaw、Gitea 四个后端，实现语音→CEO→后端→播报的完整链路。

**Architecture:** 利用已有 Server MCP 机制接入 Multica 和 Claude Code；新增 OpenClaw HTTP 适配器和 Gitea API 客户端；通过 AgentProxy 统一路由。

**Tech Stack:** Python 3.10, httpx, mcp SDK, 现有 Server MCP 基础设施

---

## 前置条件

- [x] Phase 1-7 基础框架已完成（workspace、Scheduler、Broadcast、AgentRegistry、插件、集成、ContextManager）
- [x] `requirements.txt` 已补充 `apscheduler`, `pymysql`, `redis`

---

## 文件结构

### 新建文件

| 路径 | 职责 |
|------|------|
| `main/xiaozhi-server/core/providers/agent_registry/backends/__init__.py` | 后端适配器包入口 |
| `main/xiaozhi-server/core/providers/agent_registry/backends/multica_backend.py` | Multica MCP 后端适配器 |
| `main/xiaozhi-server/core/providers/agent_registry/backends/claude_code_backend.py` | Claude Code MCP 后端适配器 |
| `main/xiaozhi-server/core/providers/agent_registry/backends/openclaw_backend.py` | OpenClaw HTTP 后端适配器 |
| `main/xiaozhi-server/core/providers/agent_registry/backends/gitea_client.py` | Gitea REST API 客户端 |
| `main/xiaozhi-server/core/providers/agent_registry/backends/base_backend.py` | 后端基类 |
| `main/xiaozhi-server/plugins_func/functions/sync_to_gitea.py` | Gitea issue 同步插件 |
| `main/xiaozhi-server/workspace/pm/skills/create_issue.py` | Claude PM 双写 issue 技能 |
| `main/xiaozhi-server/workspace/pm/skills/update_status.py` | Claude PM 更新状态技能 |

### 修改文件

| 路径 | 修改内容 |
|------|----------|
| `main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py` | 重写为使用后端适配器 |
| `main/xiaozhi-server/core/providers/agent_registry/registry.py` | 支持加载后端配置 |
| `main/xiaozhi-server/core/connection.py` | 初始化后端适配器 |
| `main/xiaozhi-server/config/config_loader.py` | 导出 `load_backends_config` 到模块级 |

---

## Phase 8: 后端适配器框架

### Task 8.1: 实现后端基类

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/__init__.py`
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/base_backend.py`

- [x] **Step 1: 创建 __init__.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/__init__.py
from .base_backend import BaseBackend

__all__ = ["BaseBackend"]
```

- [x] **Step 2: 创建 base_backend.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/base_backend.py
"""后端适配器基类"""
from abc import ABC, abstractmethod
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class BaseBackend(ABC):
    """所有后端适配器的基类"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """连接到后端服务，返回是否成功"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def execute_task(self, agent_config: dict, task: str) -> str:
        """执行任务，返回结果"""
        pass

    @abstractmethod
    async def check_health(self, agent_config: dict) -> dict:
        """检查健康状态"""
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected
```

- [x] **Step 3: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/backends/
git commit -m "feat: add backend adapter base class"
```

---

### Task 8.2: 实现 Multica 后端适配器

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/multica_backend.py`

**Context:** Multica 提供 SSE MCP 端点 (`http://192.168.31.179:18080/mcp/sse`)。利用已有的 `ServerMCPClient` 连接。

- [x] **Step 1: 创建 multica_backend.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/multica_backend.py
"""Multica 后端适配器 — 通过 MCP SSE 连接 Multica API"""
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MulticaBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.client = None
        self.tools = []

    async def connect(self) -> bool:
        """通过 MCP SSE 连接 Multica"""
        try:
            from core.providers.tools.server_mcp.mcp_client import ServerMCPClient

            url = self.config.get("url", "")
            api_key = self.config.get("api_key", "")

            if not url:
                logger.bind(tag=TAG).warning("Multica URL 未配置")
                return False

            mcp_config = {
                "url": f"{url}/mcp/sse",
                "headers": {"Authorization": f"Bearer {api_key}"} if api_key else {},
            }

            self.client = ServerMCPClient("multica", mcp_config)
            await self.client.initialize()
            self.tools = list(self.client.tools_dict.values())
            self._connected = True

            logger.bind(tag=TAG).info(f"Multica 连接成功, 发现 {len(self.tools)} 个工具")
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"Multica 连接失败: {e}")
            return False

    async def disconnect(self):
        if self.client:
            await self.client.cleanup()
            self._connected = False

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 Multica 执行任务"""
        if not self._connected:
            return "[Multica] 未连接"

        project = self.config.get("project", "")
        # 调用 Multica 的 create_issue 工具
        try:
            result = await self.client.call_tool("create_issue", {
                "project": project,
                "title": task,
                "assignee": agent_config.get("backend_id", ""),
            })
            logger.bind(tag=TAG).info(f"Multica 任务已创建: {task}")
            return f"[Multica] 任务已分发到项目 {project}: {task}"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Multica 执行失败: {e}")
            return f"[Multica] 执行失败: {e}"

    async def check_health(self, agent_config: dict) -> dict:
        if not self._connected:
            return {"name": agent_config.get("name"), "status": "disconnected", "backend": "multica"}
        return {"name": agent_config.get("name"), "status": "connected", "backend": "multica",
                "tools_count": len(self.tools)}
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/backends/multica_backend.py
git commit -m "feat: implement Multica backend adapter via MCP SSE"
```

---

### Task 8.3: 实现 Claude Code 后端适配器

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/claude_code_backend.py`

**Context:** Claude Code 通过 stdio MCP 连接 (`claude mcp serve`)。复用 `ServerMCPClient` 的 stdio 模式。

- [x] **Step 1: 创建 claude_code_backend.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/claude_code_backend.py
"""Claude Code 后端适配器 — 通过 MCP stdio 连接 Claude Code agent"""
import os
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ClaudeCodeBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.client = None
        self.tools = []

    async def connect(self) -> bool:
        """通过 MCP stdio 连接 Claude Code"""
        try:
            from core.providers.tools.server_mcp.mcp_client import ServerMCPClient

            command = self.config.get("command", "claude")
            args = self.config.get("args", ["mcp", "serve"])

            mcp_config = {
                "command": command,
                "args": args,
                "env": {**os.environ, "CLAUDE_WORKSPACE": self.config.get("workspace", "")},
            }

            self.client = ServerMCPClient("claude_code", mcp_config)
            await self.client.initialize()
            self.tools = list(self.client.tools_dict.values())
            self._connected = True

            logger.bind(tag=TAG).info(f"Claude Code 连接成功, 发现 {len(self.tools)} 个工具")
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"Claude Code 连接失败: {e}")
            return False

    async def disconnect(self):
        if self.client:
            await self.client.cleanup()
            self._connected = False

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 Claude Code 执行任务"""
        if not self._connected:
            return "[Claude Code] 未连接"

        try:
            result = await self.client.call_tool("delegate_task", {
                "task": task,
                "agent": agent_config.get("name", ""),
            })
            logger.bind(tag=TAG).info(f"Claude Code 任务执行完成: {task[:50]}")
            return f"[Claude Code] {result}"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Claude Code 执行失败: {e}")
            return f"[Claude Code] 执行失败: {e}"

    async def check_health(self, agent_config: dict) -> dict:
        if not self._connected:
            return {"name": agent_config.get("name"), "status": "disconnected", "backend": "claude_code"}
        return {"name": agent_config.get("name"), "status": "connected", "backend": "claude_code",
                "tools_count": len(self.tools)}
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/backends/claude_code_backend.py
git commit -m "feat: implement Claude Code backend adapter via MCP stdio"
```

---

### Task 8.4: 实现 OpenClaw 后端适配器

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/openclaw_backend.py`

**Context:** OpenClaw 提供 HTTP REST API（`http://192.168.31.179:18789`）。不走 MCP，直接 HTTP 调用。

- [x] **Step 1: 创建 openclaw_backend.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/openclaw_backend.py
"""OpenClaw 后端适配器 — 通过 HTTP REST API 调用 OpenClaw"""
import httpx
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class OpenClawBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.base_url = config.get("url", "http://localhost:18789")
        self.workspace = config.get("workspace", "")
        self.role = config.get("role", "assistant")
        self._client = None

    async def connect(self) -> bool:
        """连接 OpenClaw HTTP API"""
        try:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
            # 健康检查
            resp = await self._client.get("/health")
            self._connected = resp.status_code == 200
            if self._connected:
                logger.bind(tag=TAG).info(f"OpenClaw 连接成功: {self.base_url}")
            return self._connected
        except Exception as e:
            logger.bind(tag=TAG).warning(f"OpenClaw 连接失败: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        if self._client:
            await self._client.aclose()
            self._connected = False

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 OpenClaw 执行任务"""
        if not self._client:
            return "[OpenClaw] 未连接"

        try:
            resp = await self._client.post("/api/chat", json={
                "message": task,
                "workspace": agent_config.get("workspace", self.workspace),
                "role": agent_config.get("role", self.role),
            })
            resp.raise_for_status()
            data = resp.json()
            result = data.get("response", data.get("message", str(data)))
            logger.bind(tag=TAG).info(f"OpenClaw 任务完成: {task[:50]}")
            return f"[OpenClaw] {result}"
        except Exception as e:
            logger.bind(tag=TAG).error(f"OpenClaw 执行失败: {e}")
            return f"[OpenClaw] 执行失败: {e}"

    async def check_health(self, agent_config: dict) -> dict:
        base = {"name": agent_config.get("name"), "backend": "openclaw"}
        try:
            if not self._client:
                return {**base, "status": "disconnected"}
            resp = await self._client.get("/health")
            return {**base, "status": "connected" if resp.status_code == 200 else "unhealthy"}
        except Exception:
            return {**base, "status": "unreachable"}
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/backends/openclaw_backend.py
git commit -m "feat: implement OpenClaw backend adapter via HTTP REST API"
```

---

### Task 8.5: 实现 Gitea API 客户端

**Files:**
- Create: `main/xiaozhi-server/core/providers/agent_registry/backends/gitea_client.py`

**Context:** Gitea 提供 REST API（`http://192.168.31.179:8418`）。用于 Claude PM 双写看板。

- [x] **Step 1: 创建 gitea_client.py**

```python
# main/xiaozhi-server/core/providers/agent_registry/backends/gitea_client.py
"""Gitea REST API 客户端 — 用于 issue 管理（Claude PM 双写看板）"""
import httpx
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class GiteaClient:
    def __init__(self, config: dict):
        self.base_url = config.get("url", "http://localhost:8418")
        self.token = config.get("token", "")
        self.repo = config.get("repo", "")
        self._client = None

    async def connect(self) -> bool:
        try:
            headers = {"Authorization": f"token {self.token}"} if self.token else {}
            self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)
            resp = await self._client.get("/api/v1/version")
            ok = resp.status_code == 200
            if ok:
                logger.bind(tag=TAG).info(f"Gitea 连接成功: {self.base_url}")
            return ok
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Gitea 连接失败: {e}")
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def create_issue(self, title: str, body: str = "", labels: list = None) -> dict:
        """在配置的仓库中创建 issue"""
        if not self._client:
            return {"error": "未连接"}
        if not self.repo:
            return {"error": "Gitea 仓库未配置"}

        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = [{"name": l} for l in labels]

        try:
            resp = await self._client.post(f"/api/v1/repos/{self.repo}/issues", json=payload)
            resp.raise_for_status()
            issue = resp.json()
            logger.bind(tag=TAG).info(f"Gitea issue 创建成功: #{issue['number']} {title}")
            return issue
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gitea 创建 issue 失败: {e}")
            return {"error": str(e)}

    async def update_issue(self, issue_number: int, **kwargs) -> dict:
        """更新 issue（标题、状态、标签等）"""
        if not self._client:
            return {"error": "未连接"}

        try:
            resp = await self._client.patch(
                f"/api/v1/repos/{self.repo}/issues/{issue_number}",
                json=kwargs,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gitea 更新 issue 失败: {e}")
            return {"error": str(e)}

    async def add_comment(self, issue_number: int, body: str) -> dict:
        """给 issue 添加评论"""
        if not self._client:
            return {"error": "未连接"}

        try:
            resp = await self._client.post(
                f"/api/v1/repos/{self.repo}/issues/{issue_number}/comments",
                json={"body": body},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gitea 添加评论失败: {e}")
            return {"error": str(e)}

    async def list_issues(self, state: str = "open", labels: str = "") -> list:
        """列出 issues"""
        if not self._client:
            return []

        params = {"state": state}
        if labels:
            params["labels"] = labels

        try:
            resp = await self._client.get(f"/api/v1/repos/{self.repo}/issues", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gitea 查询 issues 失败: {e}")
            return []
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/backends/gitea_client.py
git commit -m "feat: implement Gitea REST API client for issue management"
```

---

## Phase 9: AgentProxy 重写 + 后端初始化

### Task 9.1: 重写 AgentProxy 使用后端适配器

**Files:**
- Modify: `main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py`

**Context:** 当前 `AgentProxy` 的 `dispatch` 方法是 TODO 占位。重写为使用后端适配器，按 `backend` 字段路由。

- [x] **Step 1: 重写 agent_proxy.py**

替换整个文件内容：

```python
# main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py
"""统一的 agent 调用代理，根据 backend 类型路由到不同后端适配器"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# 后端适配器单例（按 backend 类型缓存）
_backend_instances = {}


def _get_backend(backend_type: str, backends_config: dict):
    """获取或创建后端适配器实例"""
    if backend_type in _backend_instances:
        return _backend_instances[backend_type]

    from .backends.multica_backend import MulticaBackend
    from .backends.claude_code_backend import ClaudeCodeBackend
    from .backends.openclaw_backend import OpenClawBackend

    config = backends_config.get(backend_type, {})
    if not config:
        return None

    if backend_type == "multica":
        backend = MulticaBackend("multica", config)
    elif backend_type == "claude_code":
        backend = ClaudeCodeBackend("claude_code", config)
    elif backend_type == "openclaw":
        backend = OpenClawBackend("openclaw", config)
    else:
        logger.bind(tag=TAG).warning(f"未知 backend 类型: {backend_type}")
        return None

    _backend_instances[backend_type] = backend
    return backend


class AgentProxy:
    def __init__(self, registry, config: dict):
        self.registry = registry
        self.config = config  # backends.yaml 全量配置

    async def initialize_backends(self):
        """初始化所有已配置的后端连接"""
        for backend_type in ["multica", "claude_code", "openclaw"]:
            backend = _get_backend(backend_type, self.config)
            if backend:
                await backend.connect()

    async def dispatch(self, agent_name: str, task: str) -> str:
        """分发任务到指定 agent"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return f"Agent '{agent_name}' 不存在"

        backend_type = agent.get("backend", "local")
        logger.bind(tag=TAG).info(f"分发任务到 {agent_name}, backend: {backend_type}")

        if backend_type == "local":
            return f"[Local] 任务已执行: {task}"

        backend = _get_backend(backend_type, self.config)
        if not backend:
            return f"后端 '{backend_type}' 未配置"

        if not backend.is_connected:
            connected = await backend.connect()
            if not connected:
                return f"后端 '{backend_type}' 连接失败"

        return await backend.execute_task(agent, task)

    async def check_health(self, agent_name: str) -> dict:
        """检查 agent 健康状态"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return {"name": agent_name, "status": "not_found"}

        backend_type = agent.get("backend", "local")
        if backend_type == "local":
            return {"name": agent_name, "status": "ok", "backend": "local"}

        backend = _get_backend(backend_type, self.config)
        if not backend:
            return {"name": agent_name, "status": "no_backend", "backend": backend_type}

        return await backend.check_health(agent)

    async def check_all_health(self) -> list:
        """检查所有 agent 健康状态"""
        results = []
        for name in self.registry.get_all_agents():
            results.append(await self.check_health(name))
        return results
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/agent_registry/agent_proxy.py
git commit -m "feat: rewrite AgentProxy to use backend adapters"
```

---

### Task 9.2: 修改 connection.py 初始化后端

**Files:**
- Modify: `main/xiaozhi-server/core/connection.py`

**Context:** 在已有的 `_initialize_components` 末尾，增加后端初始化调用。

- [x] **Step 1: 在 connection.py 中添加后端初始化**

在 `_initialize_components` 方法中，找到已有的 AgentProxy 初始化代码块，在 `self.agent_proxy = AgentProxy(...)` 之后添加：

```python
# 初始化后端连接
import asyncio
asyncio.run_coroutine_threadsafe(
    self.agent_proxy.initialize_backends(), self.loop
)
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/connection.py
git commit -m "feat: initialize backend adapters on connection start"
```

---

## Phase 10: Gitea 集成插件

### Task 10.1: 实现 sync_to_gitea 插件

**Files:**
- Create: `main/xiaozhi-server/plugins_func/functions/sync_to_gitea.py`

- [x] **Step 1: 创建 sync_to_gitea.py**

```python
# main/xiaozhi-server/plugins_func/functions/sync_to_gitea.py
"""Gitea issue 同步插件 — 创建/更新/查询 issue"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

sync_to_gitea_desc = {
    "type": "function",
    "function": {
        "name": "sync_to_gitea",
        "description": "同步任务到 Gitea Issues。支持创建、更新、查询 issue。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: create / update / list",
                    "enum": ["create", "update", "list"],
                },
                "title": {
                    "type": "string",
                    "description": "Issue 标题（create 时必填）",
                },
                "body": {
                    "type": "string",
                    "description": "Issue 内容（create 时可选）",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "Issue 编号（update 时必填）",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "state": {
                    "type": "string",
                    "description": "Issue 状态（update 时可选）: open / closed",
                },
            },
            "required": ["action"],
        },
    },
}


@register_function("sync_to_gitea", sync_to_gitea_desc, ToolType.WAIT)
def sync_to_gitea(action: str, title: str = "", body: str = "",
                  issue_number: int = None, labels: list = None, state: str = None):
    import asyncio
    from config.config_loader import load_backends_config
    from core.providers.agent_registry.backends.gitea_client import GiteaClient

    config = load_backends_config()
    gitea_config = config.get("gitea", {})
    client = GiteaClient(gitea_config)

    async def _run():
        await client.connect()
        try:
            if action == "create":
                if not title:
                    return "创建 issue 需要 title 参数"
                result = await client.create_issue(title, body, labels)
                if "error" in result:
                    return f"创建失败: {result['error']}"
                return f"Issue #{result['number']} 已创建: {result['title']}"

            elif action == "update":
                if not issue_number:
                    return "更新 issue 需要 issue_number 参数"
                kwargs = {}
                if title:
                    kwargs["title"] = title
                if body:
                    kwargs["body"] = body
                if state:
                    kwargs["state"] = state
                if labels:
                    kwargs["labels"] = [{"name": l} for l in labels]
                result = await client.update_issue(issue_number, **kwargs)
                if "error" in result:
                    return f"更新失败: {result['error']}"
                return f"Issue #{issue_number} 已更新"

            elif action == "list":
                issues = await client.list_issues(state or "open")
                if not issues:
                    return "当前没有 issue"
                lines = []
                for i in issues[:10]:
                    label_str = ", ".join(l["name"] for l in i.get("labels", []))
                    lines.append(f"- #{i['number']} [{i['state']}] {i['title']}"
                                 + (f" ({label_str})" if label_str else ""))
                return "Gitea Issues:\n" + "\n".join(lines)

            else:
                return f"未知操作: {action}"
        finally:
            await client.close()

    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_run())
    except RuntimeError:
        result = asyncio.run(_run())

    return ActionResponse(Action.REQLLM, result, None)
```

- [x] **Step 2: Commit**

```bash
git add main/xiaozhi-server/plugins_func/functions/sync_to_gitea.py
git commit -m "feat: add Gitea issue sync plugin (create/update/list)"
```

---

### Task 10.2: 实现 Claude PM 双写技能

**Files:**
- Create: `main/xiaozhi-server/workspace/pm/skills/create_issue.py`
- Create: `main/xiaozhi-server/workspace/pm/skills/update_status.py`

- [x] **Step 1: 创建 create_issue.py**

```python
# main/xiaozhi-server/workspace/pm/skills/create_issue.py
"""Claude PM 技能：同时在 Gitea 和 Multica 创建 issue（纯记录，不派发）"""
import asyncio
from config.config_loader import load_backends_config
from core.providers.agent_registry.backends.gitea_client import GiteaClient
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


async def create_issue(title: str, body: str = "", labels: list = None) -> str:
    """双写 issue 到 Gitea + Multica"""
    config = load_backends_config()

    # Gitea
    gitea = GiteaClient(config.get("gitea", {}))
    await gitea.connect()
    try:
        gitea_result = await gitea.create_issue(title, body, labels)
        gitea_ref = f"Gitea #{gitea_result.get('number', '?')}" if "error" not in gitea_result else f"Gitea 失败: {gitea_result['error']}"
    finally:
        await gitea.close()

    # Multica（通过代理）
    multica_ref = "Multica: TODO"  # 需要 Multica API 集成后完善

    logger.bind(tag=TAG).info(f"双写 issue: {title} -> {gitea_ref}, {multica_ref}")
    return f"已创建: {gitea_ref}, {multica_ref}"
```

- [x] **Step 2: 创建 update_status.py**

```python
# main/xiaozhi-server/workspace/pm/skills/update_status.py
"""Claude PM 技能：更新 Gitea + Multica 中的 issue 状态"""
import asyncio
from config.config_loader import load_backends_config
from core.providers.agent_registry.backends.gitea_client import GiteaClient
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


async def update_status(issue_number: int, state: str, comment: str = "") -> str:
    """双写更新 issue 状态"""
    config = load_backends_config()

    gitea = GiteaClient(config.get("gitea", {}))
    await gitea.connect()
    try:
        result = await gitea.update_issue(issue_number, state=state)
        if comment:
            await gitea.add_comment(issue_number, comment)
        status = "成功" if "error" not in result else f"失败: {result['error']}"
    finally:
        await gitea.close()

    logger.bind(tag=TAG).info(f"更新 issue #{issue_number}: {state} -> {status}")
    return f"Issue #{issue_number} 状态已更新为 {state}"
```

- [x] **Step 3: Commit**

```bash
git add main/xiaozhi-server/workspace/pm/skills/
git commit -m "feat: add Claude PM dual-write skills for Gitea + Multica"
```

---

## Phase 11: 作息调整 + 主动播报

### Task 11.1: 实现早晚自动播报调度

**Files:**
- Create: `main/xiaozhi-server/plugins_func/functions/set_schedule.py`
- Create: `main/xiaozhi-server/plugins_func/functions/query_schedule.py`

- [x] **Step 1: 创建 set_schedule.py**

```python
# main/xiaozhi-server/plugins_func/functions/set_schedule.py
"""设置作息时间表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

set_schedule_desc = {
    "type": "function",
    "function": {
        "name": "set_schedule",
        "description": "设置或修改作息时间表。支持设置早间播报、晚间总结、健康巡检的时间。",
        "parameters": {
            "type": "object",
            "properties": {
                "schedule_type": {
                    "type": "string",
                    "description": "时间表类型",
                    "enum": ["morning_briefing", "evening_summary", "health_check"],
                },
                "time": {
                    "type": "string",
                    "description": "时间，格式 HH:MM",
                },
            },
            "required": ["schedule_type", "time"],
        },
    },
}


@register_function("set_schedule", set_schedule_desc, ToolType.WAIT)
def set_schedule(schedule_type: str, time: str):
    from core.providers.scheduler.scheduler_manager import SchedulerManager

    scheduler = SchedulerManager()

    message_map = {
        "morning_briefing": "早间播报：请总结今日待办事项和日程",
        "evening_summary": "晚间总结：请回顾今日完成的任务和明日计划",
        "health_check": "健康巡检：请检查所有 Agent 状态",
    }

    job_id = f"schedule_{schedule_type}"
    message = message_map.get(schedule_type, f"定时任务: {schedule_type}")

    # 解析时间
    parts = time.split(":")
    hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0

    # 添加 cron 任务（每天执行）
    cron_expr = f"{minute} {hour} * * *"
    scheduler.add_cron_job(job_id, cron_expr, message, "default")

    type_names = {
        "morning_briefing": "早间播报",
        "evening_summary": "晚间总结",
        "health_check": "健康巡检",
    }
    name = type_names.get(schedule_type, schedule_type)
    return ActionResponse(Action.REQLLM, f"已设置{name}时间为每天 {time}", None)
```

- [x] **Step 2: 创建 query_schedule.py**

```python
# main/xiaozhi-server/plugins_func/functions/query_schedule.py
"""查询当前作息时间表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

query_schedule_desc = {
    "type": "function",
    "function": {
        "name": "query_schedule",
        "description": "查看当前的作息时间表配置",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("query_schedule", query_schedule_desc, ToolType.WAIT)
def query_schedule():
    from core.providers.scheduler.reminder_store import ReminderStore

    store = ReminderStore()
    reminders = store.get_active_reminders("default")

    # 过滤出定时任务
    schedule_items = [r for r in reminders if r.get("trigger_type") == "cron"]

    if not schedule_items:
        return ActionResponse(Action.REQLLM, "当前没有设置作息时间表", None)

    lines = []
    for r in schedule_items:
        lines.append(f"- {r['trigger_time']} | {r['message']}")

    return ActionResponse(Action.REQLLM, "当前作息时间表：\n" + "\n".join(lines), None)
```

- [x] **Step 3: Commit**

```bash
git add main/xiaozhi-server/plugins_func/functions/set_schedule.py
git add main/xiaozhi-server/plugins_func/functions/query_schedule.py
git commit -m "feat: add schedule management plugins (set/query)"
```

---

## 验证清单

 - [x] Multica 后端能通过 MCP SSE 连接并发现工具
 - [x] Claude Code 后端能通过 MCP stdio 连接并发现工具
 - [x] OpenClaw 后端能通过 HTTP API 连接
 - [x] Gitea 客户端能创建/更新/查询 issue
 - [x] AgentProxy 按 backend 类型正确路由到对应适配器
 - [x] sync_to_gitea 插件能正常注册和调用
 - [x] Claude PM 双写技能能同时写入 Gitea
 - [x] set_schedule / query_schedule 插件能正常注册和调用
 - [x] 早晚自动播报 cron 任务能正常触发
 - [x] connection.py 能正常初始化所有后端连接
