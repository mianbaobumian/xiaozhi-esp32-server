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
