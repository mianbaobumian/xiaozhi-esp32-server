"""最小化测试：逐步骤定位卡住的位置"""
import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

print("Step 1: 导入 yaml", flush=True)
import yaml
print("  OK", flush=True)

print("Step 2: 导入 config_loader", flush=True)
from config.config_loader import load_backends_config
print("  OK", flush=True)

print("Step 3: 加载 backends 配置", flush=True)
config = load_backends_config()
print(f"  OK: workspace_path={config.get('workspace_path')}", flush=True)

print("Step 4: 导入 AgentRegistry", flush=True)
from core.providers.agent_registry.registry import AgentRegistry
print("  OK", flush=True)

print("Step 5: 创建 registry", flush=True)
registry = AgentRegistry(config.get("workspace_path", "./workspace"))
print("  OK", flush=True)

print("Step 6: 扫描 workspace", flush=True)
registry.scan_workspace()
print(f"  OK: {len(registry.agents)} agents", flush=True)

for name, cfg in registry.agents.items():
    print(f"    - {name}: backend={cfg.get('backend')}", flush=True)

print("\nStep 7: 测试 list_agents 函数", flush=True)
from plugins_func.functions.list_agents import list_agents
result = list_agents()
print(f"  {result}", flush=True)

print("\n全部完成!", flush=True)
