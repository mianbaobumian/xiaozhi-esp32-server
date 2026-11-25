"""模拟语音命令端到端测试"""
import asyncio
import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)


class MockConn:
    def __init__(self, agent_proxy, loop):
        self.agent_proxy = agent_proxy
        self.loop = loop


def get_response(result):
    """从 ActionResponse 或字符串中提取文本"""
    if hasattr(result, 'response'):
        return result.response
    return str(result)


async def setup():
    from config.config_loader import load_backends_config
    from core.providers.agent_registry.registry import AgentRegistry
    from core.providers.agent_registry.agent_proxy import AgentProxy
    from core.providers.agent_registry import agent_proxy as proxy_module
    proxy_module._backend_instances.clear()

    backends_config = load_backends_config()
    workspace_path = backends_config.get("workspace_path", "./workspace")
    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()

    proxy = AgentProxy(registry, backends_config)
    print("  连接后端 (最多30秒)...", flush=True)
    try:
        await asyncio.wait_for(proxy.initialize_backends(), timeout=30)
    except asyncio.TimeoutError:
        print("  [WARN] 部分后端连接超时，继续测试", flush=True)
    return proxy


def test_list_agents():
    print("\n" + "=" * 50, flush=True)
    print('模拟语音: "列出所有agent"', flush=True)
    print("=" * 50, flush=True)

    from plugins_func.functions.list_agents import list_agents
    result = list_agents()
    text = get_response(result)
    print(f"\n{text}", flush=True)
    return "assistant" in text and "ceo" in text


def test_health_check(proxy):
    print("\n" + "=" * 50, flush=True)
    print('模拟语音: "检查agent状态"', flush=True)
    print("=" * 50, flush=True)

    from plugins_func.functions.agent_health_check import agent_health_check
    loop = asyncio.get_event_loop()
    conn = MockConn(proxy, loop)
    result = agent_health_check(conn)
    text = get_response(result)
    print(f"\n{text}", flush=True)
    return "Agent" in text


async def test_dispatch(proxy, agent_name, task):
    print("\n" + "=" * 50, flush=True)
    print(f'模拟语音: "让{agent_name}帮我{task}"', flush=True)
    print("=" * 50, flush=True)

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    loop = asyncio.get_event_loop()
    conn = MockConn(proxy, loop)

    print("  调度中 (最多120秒)...", flush=True)
    try:
        # dispatch_to_agent 是同步函数，内部用 run_coroutine_threadsafe
        # 在 async 上下文中需要用 executor 避免死锁
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: dispatch_to_agent(conn, agent_name, task)),
            timeout=120,
        )
        text = get_response(result)
        print(f"\n{text[:500]}", flush=True)
        return "失败" not in text and "未连接" not in text
    except asyncio.TimeoutError:
        print("\n[FAIL] 超时", flush=True)
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}", flush=True)
        return False


async def main():
    print("模拟语音命令测试\n", flush=True)
    print("初始化 agent 系统...", flush=True)
    proxy = await setup()

    r1 = test_list_agents()
    r2 = test_health_check(proxy)
    r3 = await test_dispatch(proxy, "ceo", "用一句话介绍你自己")

    print("\n" + "=" * 50, flush=True)
    print("测试结果", flush=True)
    print("=" * 50, flush=True)
    print(f"  列出agent:   {'PASS' if r1 else 'FAIL'}", flush=True)
    print(f"  健康检查:    {'PASS' if r2 else 'FAIL'}", flush=True)
    print(f"  任务分发:    {'PASS' if r3 else 'FAIL'}", flush=True)

    await proxy.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
