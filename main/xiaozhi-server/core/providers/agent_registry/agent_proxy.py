"""统一的 agent 调用代理，根据 backend 类型路由到不同后端适配器"""
import asyncio
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# 后端适配器单例（按 backend 类型缓存）
_backend_instances = {}


def _get_backend(backend_type: str, backends_config: dict):
    """获取或创建后端适配器实例"""
    if backend_type in _backend_instances:
        return _backend_instances[backend_type]

    from .backends.multica_backend import MulticaBackend
    from .backends.claude_code_backend import ClaudeCodeBackend
    from .backends.openclaw_backend import OpenClawBackend

    config = backends_config.get(backend_type, {})
    if not config:
        return None

    if backend_type == "multica":
        backend = MulticaBackend("multica", config)
    elif backend_type == "claude_code":
        backend = ClaudeCodeBackend("claude_code", config)
    elif backend_type == "openclaw":
        backend = OpenClawBackend("openclaw", config)
    else:
        logger.bind(tag=TAG).warning(f"未知 backend 类型: {backend_type}")
        return None

    _backend_instances[backend_type] = backend
    return backend


class AgentProxy:
    def __init__(self, registry, config: dict):
        self.registry = registry
        self.config = config  # backends.yaml 全量配置

    async def initialize_backends(self):
        """初始化所有已配置的后端连接"""
        for backend_type in ["multica", "claude_code", "openclaw"]:
            backend = _get_backend(backend_type, self.config)
            if backend:
                await backend.connect()

    async def dispatch(self, agent_name: str, task: str) -> str:
        """分发任务到指定 agent"""
        try:
            agent = self.registry.get_agent(agent_name)
            if not agent:
                return f"Agent '{agent_name}' 不存在"

            backend_type = agent.get("backend", "local")
            logger.bind(tag=TAG).info(f"分发任务到 {agent_name}, backend: {backend_type}")

            if backend_type == "local":
                return f"[Local] 任务已执行: {task}"

            backend = _get_backend(backend_type, self.config)
            if not backend:
                return f"后端 '{backend_type}' 未配置"

            if not backend.is_connected:
                connected = await backend.connect()
                if not connected:
                    return f"后端 '{backend_type}' 连接失败"

            return await backend.execute_task(agent, task)
        except asyncio.CancelledError:
            logger.bind(tag=TAG).warning(f"dispatch 被取消: {agent_name}")
            return f"任务被取消: {agent_name}"

    async def check_health(self, agent_name: str) -> dict:
        """检查 agent 健康状态"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return {"name": agent_name, "status": "not_found"}

        backend_type = agent.get("backend", "local")
        if backend_type == "local":
            return {"name": agent_name, "status": "ok", "backend": "local"}

        backend = _get_backend(backend_type, self.config)
        if not backend:
            return {"name": agent_name, "status": "no_backend", "backend": backend_type}

        return await backend.check_health(agent)

    async def check_all_health(self) -> list:
        """检查所有 agent 健康状态"""
        results = []
        for name in self.registry.get_all_agents():
            results.append(await self.check_health(name))
        return results

    async def reset_session(self, agent_name: str) -> str:
        """重置 agent 会话（生成摘要 + 清除 session）"""
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return f"Agent '{agent_name}' 不存在"

        backend_type = agent.get("backend", "local")
        backend = _get_backend(backend_type, self.config)
        if not backend:
            return f"后端 '{backend_type}' 未配置"

        if hasattr(backend, 'reset_session'):
            return await backend.reset_session(agent_name)
        return f"后端 '{backend_type}' 不支持会话重置"

    async def shutdown(self):
        """关闭所有后端连接"""
        for backend_type, backend in _backend_instances.items():
            try:
                await backend.disconnect()
            except Exception as e:
                logger.bind(tag=TAG).warning(f"关闭后端 {backend_type} 失败: {e}")
        _backend_instances.clear()
