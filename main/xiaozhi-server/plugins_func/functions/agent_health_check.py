"""巡检所有 agent 健康状态插件"""
import asyncio
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

agent_health_check_desc = {
    "type": "function",
    "function": {
        "name": "agent_health_check",
        "description": "巡检所有 Agent 的健康状态",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("agent_health_check", agent_health_check_desc, ToolType.SYSTEM_CTL)
def agent_health_check(conn):
    """巡检所有 agent 健康状态"""
    try:
        logger.bind(tag=TAG).info("开始 Agent 健康检查")

        if not hasattr(conn, 'agent_proxy'):
            logger.bind(tag=TAG).error("conn 没有 agent_proxy 属性")
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        if not conn.agent_proxy:
            logger.bind(tag=TAG).error("conn.agent_proxy 为 None")
            return ActionResponse(Action.REQLLM, "Agent 代理未初始化", None)

        # 获取 agent 列表
        agents = conn.agent_proxy.registry.get_all_agents()
        logger.bind(tag=TAG).info(f"找到 {len(agents)} 个 agent")

        # 逐个检查健康状态
        lines = []
        for name, config in agents.items():
            backend_type = config.get("backend", "local")
            try:
                # 获取后端实例
                from core.providers.agent_registry.agent_proxy import _get_backend
                backend = _get_backend(backend_type, conn.agent_proxy.config)
                if backend:
                    if backend.is_connected:
                        lines.append(f"- {name}: 已连接 (backend: {backend_type})")
                    else:
                        lines.append(f"- {name}: 未连接 (backend: {backend_type})")
                else:
                    lines.append(f"- {name}: 后端未配置 (backend: {backend_type})")
            except Exception as e:
                logger.bind(tag=TAG).error(f"检查 {name} 失败: {e}")
                lines.append(f"- {name}: 检查失败 ({e})")

        result_text = "Agent 健康状态:\n" + "\n".join(lines)
        logger.bind(tag=TAG).info(f"Agent 健康检查完成: {len(agents)} 个 agent")
        return ActionResponse(Action.REQLLM, result_text, None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Agent 健康检查异常: {e}", exc_info=True)
        return ActionResponse(Action.REQLLM, f"Agent 健康检查失败: {e}", None)
