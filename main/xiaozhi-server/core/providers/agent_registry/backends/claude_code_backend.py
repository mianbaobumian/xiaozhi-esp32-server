"""Claude Code 后端适配器 — 通过 MCP stdio 连接 Claude Code agent"""
import asyncio
import os
import shutil
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ClaudeCodeBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.client = None
        self.tools = []
        self._use_cli_fallback = False

    async def connect(self) -> bool:
        """通过 MCP stdio 连接 Claude Code"""
        try:
            from core.providers.tools.server_mcp.mcp_client import ServerMCPClient

            command = self.config.get("command", "claude")
            args = self.config.get("args", ["mcp", "serve"])

            mcp_config = {
                "command": command,
                "args": args,
                "env": {
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", os.environ.get("USERPROFILE", "")),
                    "CLAUDE_WORKSPACE": self.config.get("workspace", ""),
                },
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

    async def _execute_via_cli(self, agent_config: dict, task: str) -> str:
        """通过 claude CLI 直接执行任务（fallback）"""
        cmd = shutil.which(self.config.get("command", "claude"))
        if not cmd:
            return "[Claude Code] CLI 命令未找到，请确认 claude 已安装并在 PATH 中"

        workspace = self.config.get("workspace", "")
        env = {**os.environ}
        if workspace:
            env["CLAUDE_WORKSPACE"] = workspace

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, "-p", task, "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace if workspace else None,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                logger.bind(tag=TAG).warning(f"Claude CLI 返回非零: {proc.returncode}, stderr: {err[:200]}")
            return output if output else "[Claude Code] CLI 无输出"
        except asyncio.TimeoutError:
            logger.bind(tag=TAG).error("Claude CLI 执行超时 (120秒)")
            return "[Claude Code] CLI 执行超时"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Claude CLI 执行异常: {e}")
            return f"[Claude Code] CLI 执行失败: {e}"

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 Claude Code 执行任务"""
        if not self._connected and not self._use_cli_fallback:
            return "[Claude Code] 未连接"

        # MCP Agent 工具不可用时直接走 CLI
        if self._use_cli_fallback:
            return await self._execute_via_cli(agent_config, task)

        try:
            result = await self.client.call_tool("Agent", {
                "description": f"执行 {agent_config.get('name', '')} agent 的任务",
                "prompt": task,
            })
            # 检查 MCP 返回的错误
            if hasattr(result, 'isError') and result.isError:
                error_text = str(result)
                if "not found" in error_text.lower() or "available agents" in error_text.lower():
                    logger.bind(tag=TAG).warning("MCP Agent 工具不可用，切换到 CLI 模式")
                    self._use_cli_fallback = True
                    return await self._execute_via_cli(agent_config, task)
                return f"[Claude Code] {result}"
            logger.bind(tag=TAG).info(f"Claude Code 任务执行完成: {task[:50]}")
            return f"[Claude Code] {result}"
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                logger.bind(tag=TAG).warning(f"MCP Agent 工具异常，切换到 CLI 模式: {e}")
                self._use_cli_fallback = True
                return await self._execute_via_cli(agent_config, task)
            logger.bind(tag=TAG).error(f"Claude Code 执行失败: {e}")
            return f"[Claude Code] 执行失败: {e}"

    async def check_health(self, agent_config: dict) -> dict:
        if not self._connected:
            return {"name": agent_config.get("name"), "status": "disconnected", "backend": "claude_code"}
        return {"name": agent_config.get("name"), "status": "connected", "backend": "claude_code",
                "tools_count": len(self.tools)}
