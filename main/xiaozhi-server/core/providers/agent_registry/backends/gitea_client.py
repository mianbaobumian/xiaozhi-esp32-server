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
