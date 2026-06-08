"""查询指定 agent 的任务状态插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

query_agent_tasks_desc = {
    "type": "function",
    "function": {
        "name": "query_agent_tasks",
        "description": "查询指定 Agent 的任务状态",
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


@register_function("query_agent_tasks", query_agent_tasks_desc, ToolType.WAIT)
def query_agent_tasks(agent_name: str):
    return ActionResponse(Action.REQLLM, f"正在查询 {agent_name} 的任务状态...", None)
