"""查询当前作息时间表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

query_schedule_desc = {
    "type": "function",
    "function": {
        "name": "query_schedule",
        "description": "查看当前的作息时间表配置",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function("query_schedule", query_schedule_desc, ToolType.WAIT)
def query_schedule():
    from core.providers.scheduler.reminder_store import ReminderStore

    store = ReminderStore()
    reminders = store.get_active_reminders("default")

    # 过滤出定时任务
    schedule_items = [r for r in reminders if r.get("trigger_type") == "cron"]

    if not schedule_items:
        return ActionResponse(Action.REQLLM, "当前没有设置作息时间表", None)

    lines = []
    for r in schedule_items:
        lines.append(f"- {r['trigger_time']} | {r['message']}")

    return ActionResponse(Action.REQLLM, "当前作息时间表：\n" + "\n".join(lines), None)
