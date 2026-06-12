"""Agent 调度流程 + 模拟语音命令测试"""
import asyncio
import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from config.config_loader import load_backends_config
from core.providers.agent_registry.registry import AgentRegistry
from core.providers.agent_registry.agent_proxy import AgentProxy
from core.providers.agent_registry import agent_proxy as proxy_module


class MockConn:
    def __init__(self, agent_proxy, loop):
        self.agent_proxy = agent_proxy
        self.loop = loop


def _text(result):
    if hasattr(result, 'result') and result.result:
        return result.result
    if hasattr(result, 'response') and result.response:
        return result.response
    return str(result)


async def create_proxy():
    proxy_module._backend_instances.clear()
    config = load_backends_config()
    registry = AgentRegistry(config.get("workspace_path", "./workspace"))
    registry.scan_workspace()
    proxy = AgentProxy(registry, config)
    await proxy.initialize_backends()
    return proxy


# ── 测试 1: 注册表 ──
async def test_registry():
    print("=" * 50)
    print("测试 1: Agent 注册表扫描")
    print("=" * 50)
    proxy = await create_proxy()
    agents = proxy.registry.get_agent_list()
    for a in agents:
        print(f"  - {a['name']}: {a['description']} (backend: {a['backend']})")
    expected = {"assistant", "reviewer", "executor", "ceo", "pm"}
    loaded = {a["name"] for a in agents}
    missing = expected - loaded
    await proxy.shutdown()
    if missing:
        print(f"\n[FAIL] 缺少: {missing}")
        return False
    print(f"\n[PASS] 全部 {len(expected)} 个 agent 已加载")
    return True


# ── 测试 2: 后端连接 ──
async def test_backend_connection():
    print("\n" + "=" * 50)
    print("测试 2: 后端连接")
    print("=" * 50)
    proxy = await create_proxy()
    results = await proxy.check_all_health()
    all_ok = True
    for r in results:
        status = r.get("status", "unknown")
        name = r.get("name", "?")
        backend = r.get("backend", "?")
        icon = "OK" if status in ("connected", "ok") else "FAIL"
        print(f"  [{icon}] {name}: {status} (backend: {backend})")
        if status not in ("connected", "ok"):
            all_ok = False
    await proxy.shutdown()
    return all_ok


# ── 测试 3: 模拟语音 "列出所有agent" ──
async def test_list_agents():
    print("\n" + "=" * 50)
    print('测试 3: 模拟语音 "列出所有agent"')
    print("=" * 50)
    from plugins_func.functions.list_agents import list_agents
    result = list_agents()
    text = _text(result)
    print(f"\n{text}")
    return "assistant" in text and "ceo" in text


# ── 测试 4: 模拟语音 "检查agent状态" ──
async def test_health_check(proxy):
    print("\n" + "=" * 50)
    print('测试 4: 模拟语音 "检查agent状态"')
    print("=" * 50)
    from plugins_func.functions.agent_health_check import agent_health_check
    conn = MockConn(proxy, asyncio.get_event_loop())
    result = agent_health_check(conn)
    text = _text(result)
    print(f"\n{text}")
    return "Agent" in text


# ── 测试 5: 模拟语音 "让CEO帮我xxx" ──
async def test_dispatch(proxy):
    print("\n" + "=" * 50)
    print('测试 5: 模拟语音 "让CEO帮我用一句话介绍你自己"')
    print("=" * 50)
    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    conn = MockConn(proxy, asyncio.get_event_loop())
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: dispatch_to_agent(conn, "ceo", "用一句话介绍你自己")
            ),
            timeout=120,
        )
        text = _text(result)
        print(f"\n{text[:500]}")
        return "失败" not in text and "未连接" not in text
    except asyncio.TimeoutError:
        print("\n[FAIL] 超时 (120秒)")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        return False


async def main():
    print("Agent 调度流程 + 模拟语音命令测试\n")

    r1 = await test_registry()
    r2 = await test_backend_connection()

    if not r1 or not r2:
        print("\n基础测试失败，跳过语音命令测试")
        return

    proxy = await create_proxy()

    r3 = await test_list_agents()
    r4 = await test_health_check(proxy)
    r5 = await test_dispatch(proxy)

    await proxy.shutdown()

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"  1. 注册表扫描:  {'PASS' if r1 else 'FAIL'}")
    print(f"  2. 后端连接:    {'PASS' if r2 else 'FAIL'}")
    print(f"  3. 列出agent:   {'PASS' if r3 else 'FAIL'}")
    print(f"  4. 健康检查:    {'PASS' if r4 else 'FAIL'}")
    print(f"  5. 任务分发:    {'PASS' if r5 else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
