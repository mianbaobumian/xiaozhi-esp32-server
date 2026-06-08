"""后端适配器基类"""
from abc import ABC, abstractmethod
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class BaseBackend(ABC):
    """所有后端适配器的基类"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """连接到后端服务，返回是否成功"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def execute_task(self, agent_config: dict, task: str) -> str:
        """执行任务，返回结果"""
        pass

    @abstractmethod
    async def check_health(self, agent_config: dict) -> dict:
        """检查健康状态"""
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected
