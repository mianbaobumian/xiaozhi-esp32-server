"""分发任务给指定 agent 插件"""
import asyncio
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

dispatch_to_agent_desc = {
    "type": "function",
    "function": {
        "name": "dispatch_to_agent",
        "description": "分发任务给指定的 Agent 执行",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称",
                },
                "task": {
                    "type": "string",
                    "description": "任务描述",
                },
            },
            "required": ["agent_name", "task"],
        },
    },
}


@register_function("dispatch_to_agent", dispatch_to_agent_desc, ToolType.SYSTEM_CTL)
def dispatch_to_agent(conn, agent_name: str, task: str):
    """分发任务给指定 agent"""
    try:
        if not hasattr(conn, 'agent_proxy') or not conn.agent_proxy:
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        # 调用异步 dispatch 方法
        loop = conn.loop
        future = asyncio.run_coroutine_threadsafe(
            conn.agent_proxy.dispatch(agent_name, task), loop
        )
        result = future.result(timeout=120)  # 2分钟超时

        logger.bind(tag=TAG).info(f"任务已分发给 {agent_name}: {task[:50]}")
        return ActionResponse(Action.REQLLM, f"CEO agent 返回结果: {result}", None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"分发任务失败: {e}")
        return ActionResponse(Action.REQLLM, f"分发任务失败: {e}", None)
