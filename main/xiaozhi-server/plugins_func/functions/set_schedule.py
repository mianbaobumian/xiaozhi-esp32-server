"""设置作息时间表插件"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

set_schedule_desc = {
    "type": "function",
    "function": {
        "name": "set_schedule",
        "description": "设置或修改作息时间表。支持设置早间播报、晚间总结、健康巡检的时间。",
        "parameters": {
            "type": "object",
            "properties": {
                "schedule_type": {
                    "type": "string",
                    "description": "时间表类型",
                    "enum": ["morning_briefing", "evening_summary", "health_check"],
                },
                "time": {
                    "type": "string",
                    "description": "时间，格式 HH:MM",
                },
            },
            "required": ["schedule_type", "time"],
        },
    },
}


@register_function("set_schedule", set_schedule_desc, ToolType.WAIT)
def set_schedule(schedule_type: str, time: str):
    from core.providers.scheduler.scheduler_manager import SchedulerManager
    from core.providers.scheduler.reminder_store import ReminderStore

    scheduler = SchedulerManager()
    store = ReminderStore()

    message_map = {
        "morning_briefing": "早间播报：请总结今日待办事项和日程",
        "evening_summary": "晚间总结：请回顾今日完成的任务和明日计划",
        "health_check": "健康巡检：请检查所有 Agent 状态",
    }

    job_id = f"schedule_{schedule_type}"
    message = message_map.get(schedule_type, f"定时任务: {schedule_type}")

    # 解析和验证时间
    try:
        parts = time.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return ActionResponse(Action.REQLLM, f"无效时间格式: {time}，小时应为 0-23，分钟应为 0-59", None)
    except (ValueError, IndexError):
        return ActionResponse(Action.REQLLM, f"无效时间格式: {time}，请使用 HH:MM 格式（如 08:30）", None)

    # 添加 cron 任务（每天执行）
    cron_expr = f"{minute} {hour} * * *"
    scheduler.add_cron_job(job_id, cron_expr, message, "default")

    # 持久化到数据库
    store.save("default", "cron", cron_expr, message)

    type_names = {
        "morning_briefing": "早间播报",
        "evening_summary": "晚间总结",
        "health_check": "健康巡检",
    }
    name = type_names.get(schedule_type, schedule_type)
    return ActionResponse(Action.REQLLM, f"已设置{name}时间为每天 {time}", None)
