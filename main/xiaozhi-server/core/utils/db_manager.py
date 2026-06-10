"""MySQL 和 Redis 连接管理"""
import json
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

_mysql_conn = None
_redis_client = None


def get_mysql_connection():
    """获取 MySQL 连接"""
    global _mysql_conn
    if _mysql_conn is not None:
        return _mysql_conn

    from config.config_loader import load_backends_config
    import pymysql

    config = load_backends_config()
    mysql_config = config.get("mysql", {})

    _mysql_conn = pymysql.connect(
        host=mysql_config.get("host", "localhost"),
        port=mysql_config.get("port", 3306),
        user=mysql_config.get("user", "root"),
        password=mysql_config.get("password", ""),
        database=mysql_config.get("database", "xiaozhi_agent"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    logger.bind(tag=TAG).info("MySQL 连接成功")
    return _mysql_conn


def get_redis_client():
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    from config.config_loader import load_backends_config
    import redis

    config = load_backends_config()
    redis_config = config.get("redis", {})

    _redis_client = redis.Redis(
        host=redis_config.get("host", "localhost"),
        port=redis_config.get("port", 6379),
        db=redis_config.get("db", 3),
        password=redis_config.get("password"),
        decode_responses=True,
    )
    logger.bind(tag=TAG).info("Redis 连接成功")
    return _redis_client


def execute_query(sql, params=None):
    """执行查询语句"""
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def execute_update(sql, params=None):
    """执行更新语句"""
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        result = cursor.execute(sql, params)
    conn.commit()
    return result
