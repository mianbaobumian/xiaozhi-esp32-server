"""查询提醒列表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

list_reminders_desc = {
    "type": "function",
    "function": {
        "name": "list_reminders",
        "description": "查看当前所有活跃的提醒列表",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("list_reminders", list_reminders_desc, ToolType.WAIT)
def list_reminders():
    from core.providers.scheduler.reminder_store import ReminderStore

    store = ReminderStore()
    reminders = store.get_active_reminders("default")

    if not reminders:
        return ActionResponse(Action.REQLLM, "当前没有活跃的提醒", None)

    lines = []
    for r in reminders:
        lines.append(f"- [{r['id'][:8]}] {r['trigger_time']} | {r['message']}")
    return ActionResponse(Action.REQLLM, "当前提醒列表：\n" + "\n".join(lines), None)
