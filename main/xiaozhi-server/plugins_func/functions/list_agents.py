"""列出所有可用 Agent 插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

list_agents_desc = {
    "type": "function",
    "function": {
        "name": "list_agents",
        "description": "列出所有可用的 Agent",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("list_agents", list_agents_desc, ToolType.WAIT)
def list_agents():
    from core.providers.agent_registry.registry import AgentRegistry
    from config.config_loader import load_backends_config

    config = load_backends_config()
    workspace_path = config.get("workspace_path", "./workspace")
    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    agents = registry.get_agent_list()
    if not agents:
        return ActionResponse(Action.REQLLM, "当前没有可用的 Agent", None)

    lines = []
    for a in agents:
        lines.append(f"- {a['name']}: {a['description']} (backend: {a['backend']})")
    return ActionResponse(Action.REQLLM, "可用 Agent 列表：\n" + "\n".join(lines), None)
