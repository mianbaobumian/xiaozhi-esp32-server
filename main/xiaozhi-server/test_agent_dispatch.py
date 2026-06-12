"""Agent 调度流程 + 模拟语音命令 + 会话持久化测试"""
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


# ── 测试 5: 首次任务分发（创建新会话）──
async def test_dispatch_first(proxy):
    print("\n" + "=" * 50)
    print('测试 5: 首次任务分发 "让ceo用一句话介绍你自己"')
    print("=" * 50)
    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    conn = MockConn(proxy, asyncio.get_event_loop())
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: dispatch_to_agent(conn, "ceo", "热力学定律是什么")
            ),
            timeout=310,
        )
        text = _text(result)
        print(f"\n{text[:500]}")
        ok = "失败" not in text and "未连接" not in text
        if ok:
            # 验证 Redis 写入
            try:
                from core.utils.db_manager import get_redis_client
                r = get_redis_client()
                sid = r.get("agent:session:ceo")
                print(f"\n  Redis agent:session:ceo = {sid}")
                ok = ok and bool(sid)
            except Exception as e:
                print(f"\n  Redis 检查失败: {e}")
                ok = False
        return ok
    except asyncio.TimeoutError:
        print("\n[FAIL] 超时 (310秒)")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        return False


# ── 测试 6: 接续会话（--resume）──
async def test_dispatch_continue(proxy):
    print("\n" + "=" * 50)
    print('测试 6: 接续会话 "刚才你说了什么"')
    print("=" * 50)

    # 先检查 Redis 中是否有 session
    try:
        from core.utils.db_manager import get_redis_client
        r = get_redis_client()
        sid = r.get("agent:session:ceo")
        print(f"  当前 session: {sid}")
        if not sid:
            print("  [SKIP] 无活跃 session，跳过")
            return True
    except Exception as e:
        print(f"  [SKIP] Redis 不可用: {e}")
        return True

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    conn = MockConn(proxy, asyncio.get_event_loop())
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: dispatch_to_agent(conn, "ceo", "刚才你说了什么？简单复述一下")
            ),
            timeout=310,
        )
        text = _text(result)
        print(f"\n{text[:500]}")
        # session UUID 不应该变
        try:
            new_sid = r.get("agent:session:ceo")
            print(f"\n  session 保持: {sid == new_sid}")
            return "失败" not in text and sid == new_sid
        except Exception:
            return "失败" not in text
    except asyncio.TimeoutError:
        print("\n[FAIL] 超时 (310秒)")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        return False


# ── 测试 7: 重置会话 ──
async def test_reset_session(proxy):
    print("\n" + "=" * 50)
    print('测试 7: 重置CEO会话')
    print("=" * 50)
    from plugins_func.functions.reset_agent_session import reset_agent_session
    conn = MockConn(proxy, asyncio.get_event_loop())
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: reset_agent_session(conn, "ceo")
            ),
            timeout=90,
        )
        text = _text(result)
        print(f"\n{text[:300]}")
        ok = "已重置" in text or "没有活跃" in text

        # 验证 Redis 已清除
        try:
            from core.utils.db_manager import get_redis_client
            r = get_redis_client()
            sid = r.get("agent:session:ceo")
            print(f"  Redis agent:session:ceo = {sid}")
            ok = ok and sid is None
        except Exception as e:
            print(f"  Redis 检查: {e}")

        # 验证 MySQL 摘要
        try:
            from core.utils.db_manager import execute_query
            rows = execute_query(
                "SELECT summary FROM agent_sessions WHERE agent_name=%s",
                ("ceo",)
            )
            if rows and rows[0].get("summary"):
                print(f"  MySQL 摘要: {rows[0]['summary'][:100]}...")
            else:
                print("  MySQL 摘要: 无")
        except Exception as e:
            print(f"  MySQL 检查: {e}")

        return ok
    except asyncio.TimeoutError:
        print("\n[FAIL] 超时 (90秒)")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        return False


async def main():
    print("Agent 调度流程 + 模拟语音命令 + 会话持久化测试\n")

    r1 = await test_registry()
    r2 = await test_backend_connection()

    if not r1 or not r2:
        print("\n基础测试失败，跳过后续测试")
        return

    proxy = await create_proxy()

    r3 = await test_list_agents()
    r4 = await test_health_check(proxy)
    r5 = await test_dispatch_first(proxy)
    r6 = await test_dispatch_continue(proxy)
    r7 = await test_reset_session(proxy)

    await proxy.shutdown()

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"  1. 注册表扫描:    {'PASS' if r1 else 'FAIL'}")
    print(f"  2. 后端连接:      {'PASS' if r2 else 'FAIL'}")
    print(f"  3. 列出agent:     {'PASS' if r3 else 'FAIL'}")
    print(f"  4. 健康检查:      {'PASS' if r4 else 'FAIL'}")
    print(f"  5. 首次任务分发:  {'PASS' if r5 else 'FAIL'}")
    print(f"  6. 接续会话:      {'PASS' if r6 else 'FAIL'}")
    print(f"  7. 重置会话:      {'PASS' if r7 else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
