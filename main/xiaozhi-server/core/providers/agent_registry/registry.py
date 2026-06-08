"""扫描 workspace/agents/ 目录，加载所有 agent config.yaml"""
import os
import yaml
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class AgentRegistry:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.agents = {}

    def scan_workspace(self):
        agents_dir = os.path.join(self.workspace_path, "agents")
        if not os.path.exists(agents_dir):
            logger.bind(tag=TAG).warning(f"agents 目录不存在: {agents_dir}")
            return

        for name in os.listdir(agents_dir):
            agent_dir = os.path.join(agents_dir, name)
            config_path = os.path.join(agent_dir, "config.yaml")
            if os.path.isdir(agent_dir) and os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    config["_dir"] = agent_dir
                    self.agents[name] = config
                    logger.bind(tag=TAG).info(f"加载 agent: {name}, backend: {config.get('backend')}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"加载 agent 失败: {name}, {e}")

        logger.bind(tag=TAG).info(f"共加载 {len(self.agents)} 个 agent")

    def get_agent(self, name: str) -> dict:
        return self.agents.get(name)

    def get_all_agents(self) -> dict:
        return self.agents

    def get_agent_list(self) -> list:
        return [
            {"name": name, "description": config.get("description", ""), "backend": config.get("backend", "")}
            for name, config in self.agents.items()
            if config.get("enabled", True)
        ]
