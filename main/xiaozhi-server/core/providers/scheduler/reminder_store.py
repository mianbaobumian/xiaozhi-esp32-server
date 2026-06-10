"""MySQL 持久化提醒任务"""
import uuid
from datetime import datetime
from core.utils.db_manager import execute_query, execute_update
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ReminderStore:
    def save(self, device_id: str, trigger_type: str, trigger_time: str, message: str) -> str:
        reminder_id = str(uuid.uuid4())
        sql = """
            INSERT INTO reminders (id, device_id, trigger_type, trigger_time, message, status, created_at)
            VALUES (%s, %s, %s, %s, %s, 'active', %s)
        """
        execute_update(sql, (reminder_id, device_id, trigger_type, trigger_time, message, datetime.now()))
        logger.bind(tag=TAG).info(f"保存提醒: {reminder_id}, 消息: {message}")
        return reminder_id

    def get_active_reminders(self, device_id: str) -> list:
        sql = "SELECT * FROM reminders WHERE device_id = %s AND status = 'active' ORDER BY created_at"
        return execute_query(sql, (device_id,))

    def get_all_active(self) -> list:
        sql = "SELECT * FROM reminders WHERE status = 'active'"
        return execute_query(sql)

    def mark_fired(self, reminder_id: str):
        sql = "UPDATE reminders SET status = 'fired', fired_at = %s WHERE id = %s"
        execute_update(sql, (datetime.now(), reminder_id))

    def delete(self, reminder_id: str):
        sql = "UPDATE reminders SET status = 'deleted' WHERE id = %s"
        execute_update(sql, (reminder_id,))
