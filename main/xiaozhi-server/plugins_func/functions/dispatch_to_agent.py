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
    future = None
    try:
        if not hasattr(conn, 'agent_proxy') or not conn.agent_proxy:
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        # 调用异步 dispatch 方法
        loop = conn.loop
        logger.bind(tag=TAG).info(f"开始分发任务给 {agent_name}: {task[:80]}")
        future = asyncio.run_coroutine_threadsafe(
            conn.agent_proxy.dispatch(agent_name, task), loop
        )
        result = future.result(timeout=310)  # 比 CLI 超时多 10 秒

        logger.bind(tag=TAG).info(f"任务已完成 {agent_name}: {result[:100] if result else 'None'}")
        return ActionResponse(Action.REQLLM, f"{agent_name} agent 返回结果: {result}", None)
    except asyncio.TimeoutError:
        if future:
            future.cancel()
        logger.bind(tag=TAG).error(f"分发任务超时: {agent_name}")
        return ActionResponse(Action.REQLLM, f"分发任务给 {agent_name} 超时", None)
    except asyncio.CancelledError:
        logger.bind(tag=TAG).warning(f"分发任务被取消: {agent_name}（可能连接已关闭）")
        return ActionResponse(Action.REQLLM, f"任务被取消: {agent_name}", None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"分发任务失败: {type(e).__name__}: {e}")
        return ActionResponse(Action.REQLLM, f"分发任务给 {agent_name} 失败: {type(e).__name__}: {e}", None)
