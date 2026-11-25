"""订阅 Redis 通知，从 MySQL 读取消息，调度 TTS 推送"""
import json
import threading
from datetime import datetime
from core.utils.db_manager import execute_query, execute_update, get_redis_client
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class BroadcastManager:
    def __init__(self, conn=None):
        self.conn = conn
        self._stop_event = threading.Event()
        self._thread = None
        logger.bind(tag=TAG).info("BroadcastManager 初始化")

    def start(self):
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        logger.bind(tag=TAG).info("BroadcastManager 已启动监听")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _listen(self):
        redis_client = get_redis_client()
        pubsub = redis_client.pubsub()
        pubsub.subscribe("broadcast:notify")
        logger.bind(tag=TAG).info("开始监听 broadcast:notify 频道")
        for message in pubsub.listen():
            if self._stop_event.is_set():
                break
            if message["type"] == "message":
                self._process_pending_messages()

    def _process_pending_messages(self):
        sql = """
            SELECT * FROM broadcast_queue
            WHERE status = 'pending' AND is_deleted = 0
            ORDER BY
                CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END,
                created_time
            LIMIT 10
        """
        messages = execute_query(sql)
        for msg in messages:
            success = self._deliver_message(msg)
            if success:
                execute_update(
                    "UPDATE broadcast_queue SET status = 'delivered', delivered_at = %s, updated_time = %s WHERE id = %s",
                    (datetime.now(), datetime.now().date(), msg["id"]),
                )
            else:
                execute_update(
                    "UPDATE broadcast_queue SET retry_count = retry_count + 1, updated_time = %s WHERE id = %s",
                    (datetime.now().date(), msg["id"]),
                )

    def _deliver_message(self, msg: dict) -> bool:
        try:
            if self.conn and hasattr(self.conn, "tts"):
                from core.providers.tts.dto.dto import TTSMessageDTO, ContentType, SentenceType
                tts_msg = TTSMessageDTO(
                    content_type=ContentType.TEXT,
                    sentence_type=SentenceType.FIRST,
                    content=msg["content"],
                )
                self.conn.tts.tts_text_queue.put(tts_msg)
                logger.bind(tag=TAG).info(f"推送消息: {msg['id']}, 内容: {msg['content'][:50]}")
                return True
            else:
                logger.bind(tag=TAG).warning(f"无连接，跳过消息: {msg['id']}")
                return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"推送失败: {msg['id']}, {e}")
            return False

    def enqueue(self, source: str, priority: str, content: str):
        sql = """
            INSERT INTO broadcast_queue (source, priority, content, status, created_time)
            VALUES (%s, %s, %s, 'pending', %s)
        """
        execute_update(sql, (source, priority, content, datetime.now().date()))
        redis_client = get_redis_client()
        redis_client.publish("broadcast:notify", json.dumps({"source": source}))
        logger.bind(tag=TAG).info(f"消息入队: source={source}, priority={priority}")
