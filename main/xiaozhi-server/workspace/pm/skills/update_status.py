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
