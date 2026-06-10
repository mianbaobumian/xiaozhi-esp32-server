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
        # 扫描 workspace/agents/ 目录
        agents_dir = os.path.join(self.workspace_path, "agents")
        if os.path.exists(agents_dir):
            for name in os.listdir(agents_dir):
                agent_dir = os.path.join(agents_dir, name)
                config_path = os.path.join(agent_dir, "config.yaml")
                if os.path.isdir(agent_dir) and os.path.exists(config_path):
                    self._load_agent(name, agent_dir, config_path)

        # 扫描 workspace 根目录下的 agent（如 ceo、pm）
        if os.path.exists(self.workspace_path):
            for name in os.listdir(self.workspace_path):
                agent_dir = os.path.join(self.workspace_path, name)
                config_path = os.path.join(agent_dir, "config.yaml")
                if os.path.isdir(agent_dir) and os.path.exists(config_path):
                    # 跳过非 agent 目录
                    if name in ("agents", "broadcast"):
                        continue
                    # 跳过已加载的
                    if name in self.agents:
                        continue
                    self._load_agent(name, agent_dir, config_path)

        logger.bind(tag=TAG).info(f"共加载 {len(self.agents)} 个 agent")

    def _load_agent(self, name: str, agent_dir: str, config_path: str):
        """加载单个 agent 配置"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            config["_dir"] = agent_dir
            self.agents[name] = config
            logger.bind(tag=TAG).info(f"加载 agent: {name}, backend: {config.get('backend')}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"加载 agent 失败: {name}, {e}")

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
