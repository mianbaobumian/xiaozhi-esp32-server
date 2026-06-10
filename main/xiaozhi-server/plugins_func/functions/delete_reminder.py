"""删除提醒插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

delete_reminder_desc = {
    "type": "function",
    "function": {
        "name": "delete_reminder",
        "description": "删除指定的提醒",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "提醒 ID（完整 ID 或前 8 位）",
                },
            },
            "required": ["reminder_id"],
        },
    },
}


@register_function("delete_reminder", delete_reminder_desc, ToolType.WAIT)
def delete_reminder(reminder_id: str):
    from core.providers.scheduler.reminder_store import ReminderStore
    from core.providers.scheduler.scheduler_manager import SchedulerManager

    store = ReminderStore()
    store.delete(reminder_id)
    scheduler = SchedulerManager()
    scheduler.remove_job(reminder_id)
    return ActionResponse(Action.REQLLM, f"已删除提醒 {reminder_id[:8]}", None)
