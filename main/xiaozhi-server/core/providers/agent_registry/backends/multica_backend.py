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

            self.client = ServerMCPClient(mcp_config)
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
