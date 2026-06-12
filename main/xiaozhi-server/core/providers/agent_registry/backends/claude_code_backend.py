"""Claude Code 后端适配器 — 通过 CLI 子进程执行任务，支持会话持久化"""
import asyncio
import os
import shutil
import uuid
from .base_backend import BaseBackend
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

REDIS_TTL = 86400  # 24 小时


class ClaudeCodeBackend(BaseBackend):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.client = None
        self.tools = []

    async def connect(self) -> bool:
        """验证 claude CLI 可用（懒连接，不启动 MCP 子进程）"""
        cmd = shutil.which(self.config.get("command", "claude"))
        if not cmd:
            logger.bind(tag=TAG).error("claude CLI 未找到，请确认已安装并在 PATH 中")
            return False

        self._connected = True
        logger.bind(tag=TAG).info("Claude Code 后端就绪（懒连接，任务执行时启动 CLI）")
        return True

    async def _ensure_mcp(self):
        """按需建立 MCP 连接（仅用于工具发现/健康检查）"""
        if self.client:
            return True
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
            logger.bind(tag=TAG).info(f"MCP 连接成功, 发现 {len(self.tools)} 个工具")
            return True
        except Exception as e:
            logger.bind(tag=TAG).warning(f"MCP 连接失败: {e}")
            return False

    async def disconnect(self):
        if self.client:
            await self.client.cleanup()
            self.client = None
        self._connected = False

    # ── 会话持久化 ──

    def _get_session(self, agent_name: str):
        """从 Redis/MySQL 获取 session UUID 和摘要。返回 (session_id|None, summary|None)"""
        redis_key = f"agent:session:{agent_name}"

        # 优先读 Redis
        try:
            from core.utils.db_manager import get_redis_client
            r = get_redis_client()
            sid = r.get(redis_key)
            if sid:
                logger.bind(tag=TAG).debug(f"Redis 命中 {redis_key}: {sid}")
                return sid, None
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Redis 读取失败: {e}")

        # Redis 未命中，读 MySQL
        try:
            from core.utils.db_manager import execute_query
            rows = execute_query(
                "SELECT session_id, summary FROM agent_sessions WHERE agent_name=%s",
                (agent_name,)
            )
            if rows:
                row = rows[0]
                sid = row["session_id"]
                summary = row.get("summary")
                # 回写 Redis
                try:
                    r = get_redis_client()
                    r.setex(redis_key, REDIS_TTL, sid)
                except Exception:
                    pass
                logger.bind(tag=TAG).info(f"MySQL 命中 {agent_name}: session={sid}, has_summary={bool(summary)}")
                return sid, summary
        except Exception as e:
            logger.bind(tag=TAG).warning(f"MySQL 读取失败: {e}")

        return None, None

    def _save_session(self, agent_name: str, session_id: str):
        """保存 session UUID 到 Redis + MySQL"""
        redis_key = f"agent:session:{agent_name}"

        # Redis
        try:
            from core.utils.db_manager import get_redis_client
            r = get_redis_client()
            r.setex(redis_key, REDIS_TTL, session_id)
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Redis 写入失败: {e}")

        # MySQL UPSERT
        try:
            from core.utils.db_manager import execute_update
            execute_update(
                "INSERT INTO agent_sessions (agent_name, session_id) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE session_id=%s, updated_at=NOW()",
                (agent_name, session_id, session_id)
            )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"MySQL 写入失败: {e}")

    def _save_summary(self, agent_name: str, summary: str):
        """保存摘要到 MySQL"""
        try:
            from core.utils.db_manager import execute_update
            execute_update(
                "UPDATE agent_sessions SET summary=%s, updated_at=NOW() WHERE agent_name=%s",
                (summary, agent_name)
            )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"MySQL 摘要写入失败: {e}")

    def _clear_session(self, agent_name: str):
        """清除 Redis + MySQL 中的 session"""
        redis_key = f"agent:session:{agent_name}"
        try:
            from core.utils.db_manager import get_redis_client
            r = get_redis_client()
            r.delete(redis_key)
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Redis 删除失败: {e}")
        try:
            from core.utils.db_manager import execute_update
            execute_update(
                "DELETE FROM agent_sessions WHERE agent_name=%s",
                (agent_name,)
            )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"MySQL 删除失败: {e}")

    async def _generate_summary(self, old_session_id: str) -> str:
        """用旧 session 提炼摘要"""
        cmd = shutil.which(self.config.get("command", "claude"))
        if not cmd:
            return ""

        workspace = self.config.get("workspace", "")
        env = {**os.environ}
        if workspace:
            env["CLAUDE_WORKSPACE"] = workspace

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, "-p", "请用3句话总结我们之前的对话要点，直接输出摘要内容",
                "--output-format", "text",
                "--dangerously-skip-permissions",
                "--resume", old_session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace if workspace else None,
                env=env,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode("utf-8", errors="replace").strip()
            return output if output else ""
        except Exception as e:
            logger.bind(tag=TAG).warning(f"摘要生成失败: {e}")
            return ""

    # ── CLI 执行 ──

    async def _run_cli(self, cmd: str, args: list, workspace: str, env: dict, timeout: int) -> tuple[int, str]:
        """执行 claude CLI 子进程，返回 (returncode, output)"""
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace if workspace else None,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                logger.bind(tag=TAG).warning(f"Claude CLI 返回非零: {proc.returncode}, stderr: {err[:200]}")
                return proc.returncode, err or output
            return 0, output if output else "[Claude Code] CLI 无输出"
        except asyncio.TimeoutError:
            logger.bind(tag=TAG).error(f"Claude CLI 执行超时 ({timeout}秒)")
            return -1, f"[Claude Code] CLI 执行超时 ({timeout}秒)"
        except Exception as e:
            logger.bind(tag=TAG).error(f"Claude CLI 执行异常: {e}")
            return -1, f"[Claude Code] CLI 执行失败: {e}"

    def _build_cli_args(self, prompt: str, session_id: str | None = None, resume_id: str | None = None) -> list:
        """构造 CLI 参数"""
        args = ["-p", prompt, "--output-format", "text", "--dangerously-skip-permissions"]
        if resume_id:
            args.extend(["--resume", resume_id])
        elif session_id:
            args.extend(["--session-id", session_id])
        return args

    async def _execute_via_cli(self, agent_config: dict, task: str) -> str:
        """通过 claude CLI 执行任务，支持会话持久化"""
        cmd = shutil.which(self.config.get("command", "claude"))
        if not cmd:
            return "[Claude Code] CLI 命令未找到，请确认 claude 已安装并在 PATH 中"

        agent_name = agent_config.get("name", "unknown")
        workspace = self.config.get("workspace", "")
        env = {**os.environ}
        if workspace:
            env["CLAUDE_WORKSPACE"] = workspace
        timeout = self.config.get("timeout", 300)

        # 读取已有 session
        old_session_id, summary = self._get_session(agent_name)

        if old_session_id:
            # 尝试接续已有会话
            logger.bind(tag=TAG).info(f"接续会话 {agent_name}: {old_session_id[:8]}...")
            cli_args = self._build_cli_args(task, resume_id=old_session_id)
            code, result = await self._run_cli(cmd, cli_args, workspace, env, timeout)

            if code == 0:
                self._save_session(agent_name, old_session_id)
                return result

            # resume 失败（session 不存在/过期），清除旧记录，走新建流程
            logger.bind(tag=TAG).warning(f"接续会话失败 (code={code})，清除旧 session 并创建新会话")
            self._clear_session(agent_name)
            old_session_id = None
            summary = None

        # 新建会话
        new_session_id = str(uuid.uuid4())
        prompt = task
        if summary:
            prompt = f"之前的对话摘要:\n{summary}\n\n当前任务:\n{task}"
        cli_args = self._build_cli_args(prompt, session_id=new_session_id)
        logger.bind(tag=TAG).info(f"创建新会话 {agent_name}: {new_session_id[:8]}...")

        code, result = await self._run_cli(cmd, cli_args, workspace, env, timeout)

        if code == 0:
            self._save_session(agent_name, new_session_id)
        else:
            logger.bind(tag=TAG).warning(f"新建会话失败 (code={code})，不保存 session")

        return result

    async def execute_task(self, agent_config: dict, task: str) -> str:
        """通过 Claude Code CLI 执行任务"""
        if not self._connected:
            return "[Claude Code] 未连接"

        logger.bind(tag=TAG).info(f"Claude Code 开始执行任务: {task[:80]}")
        return await self._execute_via_cli(agent_config, task)

    async def check_health(self, agent_config: dict) -> dict:
        if not self._connected:
            return {"name": agent_config.get("name"), "status": "disconnected", "backend": "claude_code"}
        cmd = shutil.which(self.config.get("command", "claude"))
        status = "connected" if cmd else "cli_not_found"
        return {"name": agent_config.get("name"), "status": status, "backend": "claude_code"}

    async def reset_session(self, agent_name: str) -> str:
        """重置 agent 会话：生成摘要 → 存 MySQL → 清除 Redis"""
        old_sid, _ = self._get_session(agent_name)
        if not old_sid:
            return f"Agent '{agent_name}' 没有活跃会话"

        summary = await self._generate_summary(old_sid)
        if summary:
            self._save_summary(agent_name, summary)
            logger.bind(tag=TAG).info(f"已保存 {agent_name} 摘要: {summary[:80]}...")

        # 清除 Redis，下次调用自动创建新会话
        try:
            from core.utils.db_manager import get_redis_client
            r = get_redis_client()
            r.delete(f"agent:session:{agent_name}")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Redis 删除失败: {e}")

        return f"已重置 {agent_name} 会话" + ("，已保存摘要" if summary else "")
