"""重置 Agent 会话（生成摘要 + 清除 session）"""
import asyncio
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

reset_agent_session_desc = {
    "type": "function",
    "function": {
        "name": "reset_agent_session",
        "description": "重置指定 Agent 的会话记忆，下次对话将开始新会话",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "要重置的 Agent 名称",
                },
            },
            "required": ["agent_name"],
        },
    },
}


@register_function("reset_agent_session", reset_agent_session_desc, ToolType.SYSTEM_CTL)
def reset_agent_session(conn, agent_name: str):
    """重置指定 agent 的会话"""
    future = None
    try:
        if not hasattr(conn, 'agent_proxy') or not conn.agent_proxy:
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        loop = conn.loop
        logger.bind(tag=TAG).info(f"重置会话: {agent_name}")
        future = asyncio.run_coroutine_threadsafe(
            conn.agent_proxy.reset_session(agent_name), loop
        )
        result = future.result(timeout=90)

        return ActionResponse(Action.REQLLM, result, None)
    except asyncio.TimeoutError:
        if future:
            future.cancel()
        return ActionResponse(Action.REQLLM, f"重置 {agent_name} 会话超时", None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"重置会话失败: {type(e).__name__}: {e}")
        return ActionResponse(Action.REQLLM, f"重置 {agent_name} 会话失败: {e}", None)
