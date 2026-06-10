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
