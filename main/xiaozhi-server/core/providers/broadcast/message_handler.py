"""消息优先级处理和设备空闲检测"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MessageHandler:
    def __init__(self, conn):
        self.conn = conn

    def is_device_idle(self) -> bool:
        if self.conn is None:
            return True
        return not getattr(self.conn, "client_is_speaking", False)

    def should_deliver(self, priority: str) -> bool:
        if priority == "high":
            return True
        if priority == "normal":
            return self.is_device_idle()
        if priority == "low":
            return self.is_device_idle()
        return False
