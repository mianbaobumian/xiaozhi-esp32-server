"""设置提醒插件"""
from datetime import datetime, timedelta
from plugins_func.register import register_function, ToolType, ActionResponse, Action

set_reminder_desc = {
    "type": "function",
    "function": {
        "name": "set_reminder",
        "description": "设置提醒。支持一次性提醒（指定时间）和周期性提醒（cron 表达式）。",
        "parameters": {
            "type": "object",
            "properties": {
                "time": {
                    "type": "string",
                    "description": "提醒时间。格式：'YYYY-MM-DD HH:MM'（一次性）、'HH:MM'（每天）、'+10m'（10分钟后）、'0 8 * * *'（cron）",
                },
                "message": {
                    "type": "string",
                    "description": "提醒内容",
                },
                "repeat": {
                    "type": "boolean",
                    "description": "是否重复，默认 false",
                },
            },
            "required": ["time", "message"],
        },
    },
}


@register_function("set_reminder", set_reminder_desc, ToolType.WAIT)
def set_reminder(time: str, message: str, repeat: bool = False):
    from core.providers.scheduler.scheduler_manager import SchedulerManager
    from core.providers.scheduler.reminder_store import ReminderStore
    import uuid

    store = ReminderStore()
    scheduler = SchedulerManager()
    job_id = str(uuid.uuid4())

    if time.startswith("+"):
        minutes = int(time.replace("+", "").replace("m", ""))
        run_date = datetime.now() + timedelta(minutes=minutes)
        trigger_type = "date"
        trigger_time = run_date.isoformat()
        store.save("default", trigger_type, trigger_time, message)
        scheduler.add_once_job(job_id, run_date, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，{minutes}分钟后提醒你：{message}", None)
    elif repeat:
        trigger_type = "cron"
        store.save("default", trigger_type, time, message)
        scheduler.add_cron_job(job_id, time, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，已设置周期性提醒：{message}", None)
    else:
        run_date = datetime.fromisoformat(time)
        trigger_type = "date"
        store.save("default", trigger_type, time, message)
        scheduler.add_once_job(job_id, run_date, message, "default")
        return ActionResponse(Action.REQLLM, f"好的，将在 {time} 提醒你：{message}", None)
