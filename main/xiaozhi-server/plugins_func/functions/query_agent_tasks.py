"""查询指定 agent 的健康状态插件"""
import asyncio
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

query_agent_tasks_desc = {
    "type": "function",
    "function": {
        "name": "query_agent_tasks",
        "description": "查询指定 Agent 的健康状态",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称",
                },
            },
            "required": ["agent_name"],
        },
    },
}


@register_function("query_agent_tasks", query_agent_tasks_desc, ToolType.SYSTEM_CTL)
def query_agent_tasks(conn, agent_name: str):
    """查询指定 agent 的健康状态"""
    try:
        logger.bind(tag=TAG).info(f"开始查询 {agent_name} 健康状态")

        if not hasattr(conn, 'agent_proxy'):
            logger.bind(tag=TAG).error("conn 没有 agent_proxy 属性")
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        if not conn.agent_proxy:
            logger.bind(tag=TAG).error("conn.agent_proxy 为 None")
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        # 获取 agent 配置
        agent_config = conn.agent_proxy.registry.get_agent(agent_name)
        if not agent_config:
            return ActionResponse(Action.REQLLM, f"Agent '{agent_name}' 不存在", None)

        backend_type = agent_config.get("backend", "local")

        # 获取后端实例
        from core.providers.agent_registry.agent_proxy import _get_backend
        backend = _get_backend(backend_type, conn.agent_proxy.config)

        if not backend:
            result_text = f"{agent_name} 状态: 后端未配置 (backend: {backend_type})"
        elif backend.is_connected:
            result_text = f"{agent_name} 状态: 已连接 (backend: {backend_type})"
        else:
            result_text = f"{agent_name} 状态: 未连接 (backend: {backend_type})"

        logger.bind(tag=TAG).info(f"Agent 健康查询完成: {agent_name}")
        return ActionResponse(Action.REQLLM, result_text, None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Agent 健康查询异常: {e}", exc_info=True)
        return ActionResponse(Action.REQLLM, f"查询 {agent_name} 健康状态失败: {e}", None)
