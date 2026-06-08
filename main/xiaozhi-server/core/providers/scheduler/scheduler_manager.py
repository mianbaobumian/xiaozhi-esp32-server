"""APScheduler 封装，管理定时任务"""
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from core.utils.db_manager import execute_update, get_redis_client
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.bind(tag=TAG).info("SchedulerManager 已启动")

    def add_once_job(self, job_id: str, run_date: datetime, message: str, device_id: str):
        trigger = DateTrigger(run_date=run_date)
        self.scheduler.add_job(
            self._fire_reminder, trigger=trigger, id=job_id,
            args=[job_id, message, device_id], replace_existing=True,
        )
        logger.bind(tag=TAG).info(f"添加一次性任务: {job_id}, 时间: {run_date}")

    def add_cron_job(self, job_id: str, cron_expr: str, message: str, device_id: str):
        parts = cron_expr.split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
        )
        self.scheduler.add_job(
            self._fire_reminder, trigger=trigger, id=job_id,
            args=[job_id, message, device_id], replace_existing=True,
        )
        logger.bind(tag=TAG).info(f"添加周期任务: {job_id}, cron: {cron_expr}")

    def remove_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            logger.bind(tag=TAG).info(f"移除任务: {job_id}")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"移除任务失败: {job_id}, {e}")

    def _fire_reminder(self, job_id: str, message: str, device_id: str):
        try:
            sql = """
                INSERT INTO broadcast_queue (source, priority, content, status, created_at)
                VALUES ('scheduler', 'normal', %s, 'pending', %s)
            """
            execute_update(sql, (message, datetime.now()))
            redis_client = get_redis_client()
            redis_client.publish("broadcast:notify", json.dumps({"source": "scheduler"}))
            from core.providers.scheduler.reminder_store import ReminderStore
            store = ReminderStore()
            store.mark_fired(job_id)
            logger.bind(tag=TAG).info(f"提醒已触发: {job_id}, 消息: {message}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"触发提醒失败: {job_id}, {e}")

    def restore_jobs(self, reminders: list):
        for r in reminders:
            if r["trigger_type"] == "date":
                run_date = datetime.fromisoformat(r["trigger_time"])
                if run_date > datetime.now():
                    self.add_once_job(r["id"], run_date, r["message"], r["device_id"])
            elif r["trigger_type"] == "cron":
                self.add_cron_job(r["id"], r["trigger_time"], r["message"], r["device_id"])
        logger.bind(tag=TAG).info(f"恢复 {len(reminders)} 个定时任务")

    def shutdown(self):
        self.scheduler.shutdown()
