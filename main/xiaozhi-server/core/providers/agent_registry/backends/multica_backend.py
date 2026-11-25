"""Multica 后端适配器 — 通过 multica CLI 创建 issue 分发任务"""
import asyncio
import json
import shutil
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MulticaBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._cmd = None
        self.tools = []

    async def _run_cli(self, *args: str, timeout: int = 30) -> tuple[int, str, str]:
        """执行 multica CLI 命令，返回 (returncode, stdout, stderr)"""
        proc = await asyncio.create_subprocess_exec(
            self._cmd, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            proc.returncode,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def connect(self) -> bool:
        """验证 multica CLI 可用且能连通服务"""
        self._cmd = shutil.which("multica")
        if not self._cmd:
            logger.bind(tag=TAG).error("multica CLI 未找到，请确认已安装并在 PATH 中")
            return False

        try:
            code, out, err = await self._run_cli("issue", "list", "--limit", "1")
            if code != 0:
                logger.bind(tag=TAG).error(f"Multica 连接失败: {err}")
                return False
            self._connected = True
            logger.bind(tag=TAG).info("Multica 连接成功")
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"Multica 连接失败: {e}")
            return False

    async def disconnect(self):
        self._connected = False

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 multica issue create 创建任务"""
        if not self._connected:
            return "[Multica] 未连接"

        assignee = agent_config.get("backend_id", "") or agent_config.get("name", "")
        project = self.config.get("project", "")

        cmd_args = [
            "issue", "create",
            "--title", task,
            "--output", "json",
        ]
        if assignee:
            cmd_args.extend(["--assignee", assignee])
        if project:
            cmd_args.extend(["--project", project])

        try:
            code, out, err = await self._run_cli(*cmd_args, timeout=30)
            if code != 0:
                logger.bind(tag=TAG).error(f"Multica 创建 issue 失败: {err}")
                return f"[Multica] 创建失败: {err}"

            issue = json.loads(out)
            issue_key = issue.get("key", "unknown")
            logger.bind(tag=TAG).info(f"Multica 任务已创建: {issue_key}")
            return f"[Multica] 任务 {issue_key} 已创建: {task}"
        except json.JSONDecodeError:
            logger.bind(tag=TAG).warning(f"Multica 返回非 JSON: {out[:200]}")
            return f"[Multica] 任务已创建（非标准响应）"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Multica 执行失败: {e}")
            return f"[Multica] 执行失败: {e}"

    async def check_health(self, agent_config: dict) -> dict:
        if not self._connected:
            return {"name": agent_config.get("name"), "status": "disconnected", "backend": "multica"}
        try:
            code, _, _ = await self._run_cli("issue", "list", "--limit", "1")
            status = "connected" if code == 0 else "error"
        except Exception:
            status = "error"
        return {"name": agent_config.get("name"), "status": status, "backend": "multica"}
