"""巡检所有 agent 健康状态插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

agent_health_check_desc = {
    "type": "function",
    "function": {
        "name": "agent_health_check",
        "description": "巡检所有 Agent 的健康状态",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("agent_health_check", agent_health_check_desc, ToolType.WAIT)
def agent_health_check():
    return ActionResponse(Action.REQLLM, "正在巡检所有 Agent 状态...", None)
