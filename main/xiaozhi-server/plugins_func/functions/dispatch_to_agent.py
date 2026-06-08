"""分发任务给指定 agent 插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

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


@register_function("dispatch_to_agent", dispatch_to_agent_desc, ToolType.WAIT)
def dispatch_to_agent(agent_name: str, task: str):
    return ActionResponse(Action.REQLLM, f"已将任务分发给 {agent_name}: {task}", None)
