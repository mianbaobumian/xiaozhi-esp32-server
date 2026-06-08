"""统一的 agent 调用代理，根据 backend 类型路由到不同后端"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class AgentProxy:
    def __init__(self, registry, config: dict):
        self.registry = registry
        self.config = config

    async def dispatch(self, agent_name: str, task: str) -> str:
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return f"Agent '{agent_name}' 不存在"

        backend = agent.get("backend", "local")
        logger.bind(tag=TAG).info(f"分发任务到 {agent_name}, backend: {backend}")

        if backend == "multica":
            return await self._dispatch_multica(agent, task)
        elif backend == "claude_code":
            return await self._dispatch_claude_code(agent, task)
        elif backend == "openclaw":
            return await self._dispatch_openclaw(agent, task)
        elif backend == "local":
            return await self._dispatch_local(agent, task)
        else:
            return f"未知 backend: {backend}"

    async def _dispatch_multica(self, agent: dict, task: str) -> str:
        return f"[Multica] 任务已分发: {task}"

    async def _dispatch_claude_code(self, agent: dict, task: str) -> str:
        return f"[Claude Code] 任务已分发: {task}"

    async def _dispatch_openclaw(self, agent: dict, task: str) -> str:
        return f"[OpenClaw] 任务已分发: {task}"

    async def _dispatch_local(self, agent: dict, task: str) -> str:
        return f"[Local] 任务已执行: {task}"

    async def check_health(self, agent_name: str) -> dict:
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return {"name": agent_name, "status": "not_found"}
        return {"name": agent_name, "status": "unknown", "backend": agent.get("backend")}

    async def check_all_health(self) -> list:
        results = []
        for name in self.registry.get_all_agents():
            results.append(await self.check_health(name))
        return results
