"""Agent 调度流程端到端测试"""
import asyncio
import sys
import os

# 切换工作目录到项目根目录（与 app.py 一致）
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from config.config_loader import load_backends_config
from core.providers.agent_registry.registry import AgentRegistry
from core.providers.agent_registry.agent_proxy import AgentProxy


async def test_registry():
    """测试 1: Agent 注册表扫描"""
    print("=" * 50)
    print("测试 1: Agent 注册表扫描")
    print("=" * 50)

    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")

    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    agents = registry.get_agent_list()
    print(f"\n加载了 {len(agents)} 个 agent:")
    for a in agents:
        print(f"  - {a['name']}: {a['description']} (backend: {a['backend']})")

    expected = {"assistant", "reviewer", "executor", "ceo", "pm"}
    loaded = {a["name"] for a in agents}
    missing = expected - loaded

    if missing:
        print(f"\n[FAIL] 缺少 agent: {missing}")
        return False
    else:
        print(f"\n[PASS] 全部 {len(expected)} 个 agent 已加载")
        return True


async def test_backend_connection():
    """测试 2: 后端连接"""
    print("\n" + "=" * 50)
    print("测试 2: 后端连接")
    print("=" * 50)

    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")

    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    proxy = AgentProxy(registry, backends_config)

    print("\n正在连接后端...")
    await proxy.initialize_backends()

    results = await proxy.check_all_health()
    all_ok = True
    for r in results:
        status = r.get("status", "unknown")
        backend = r.get("backend", "unknown")
        name = r.get("name", "?")
        icon = "OK" if status == "connected" else "FAIL"
        print(f"  [{icon}] {name}: {status} (backend: {backend})")
        if status not in ("connected", "ok"):
            all_ok = False

    await proxy.shutdown()
    return all_ok


async def test_dispatch():
    """测试 3: 任务分发"""
    print("\n" + "=" * 50)
    print("测试 3: 任务分发 (ceo agent)")
    print("=" * 50)

    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")

    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    proxy = AgentProxy(registry, backends_config)
    await proxy.initialize_backends()

    # 先探测 Claude Code MCP 的 Agent 工具参数
    from core.providers.agent_registry.agent_proxy import _get_backend
    backend = _get_backend("claude_code", backends_config)
    if backend and backend.client:
        agent_tool = backend.client.tools_dict.get("Agent")
        if agent_tool:
            schema = agent_tool.inputSchema
            print(f"\nAgent 工具参数 schema: {schema}")
            # 检查 subagent_type 是否有 enum 约束
            props = schema.get("properties", {})
            subagent = props.get("subagent_type", {})
            if "enum" in subagent:
                print(f"可用 agent 类型: {subagent['enum']}")
            else:
                print("subagent_type 无 enum 约束，可能支持任意值")
        else:
            print("\n[MCP 中未找到 Agent 工具]")

    task = "请用一句话介绍你自己"
    print(f"\n分发任务: '{task}' -> ceo")

    try:
        result = await asyncio.wait_for(proxy.dispatch("ceo", task), timeout=60)
        print(f"结果: {result[:500]}")
        success = "失败" not in result and "未连接" not in result and "Error" not in result
    except asyncio.TimeoutError:
        print("[FAIL] 任务超时 (60秒)")
        success = False
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        success = False

    await proxy.shutdown()
    return success


async def main():
    print("Agent 调度流程测试\n")

    r1 = await test_registry()
    r2 = await test_backend_connection()

    if not r1:
        print("\n注册表测试失败，跳过调度测试")
        return

    if not r2:
        print("\n后端连接失败，跳过调度测试")
        return

    r3 = await test_dispatch()

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"  注册表扫描: {'PASS' if r1 else 'FAIL'}")
    print(f"  后端连接:   {'PASS' if r2 else 'FAIL'}")
    print(f"  任务分发:   {'PASS' if r3 else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
