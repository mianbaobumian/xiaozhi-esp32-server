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

            self.client = ServerMCPClient(mcp_config)
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
