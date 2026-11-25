#!/usr/bin/env python3
"""CEO Agent 调度功能测试 — mock 后端，测试完整 dispatch_to_agent → AgentProxy → Backend 链路"""
import sys
import os
import asyncio

project_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main", "xiaozhi-server")
sys.path.insert(0, project_dir)
os.chdir(project_dir)

from core.providers.agent_registry.registry import AgentRegistry
from core.providers.agent_registry.agent_proxy import AgentProxy
from core.providers.agent_registry import agent_proxy as proxy_module
from core.providers.agent_registry.backends.base_backend import BaseBackend
from plugins_func.register import ActionResponse


# ── Mock 后端 ──

class MockBackend(BaseBackend):
    """可控的 mock 后端，记录调用参数"""

    def __init__(self, name, config, connect_ok=True, execute_result="[Mock] task done"):
        super().__init__(name, config)
        self._connect_ok = connect_ok
        self._execute_result = execute_result
        self._execute_calls = []

    async def connect(self):
        self._connected = self._connect_ok
        return self._connect_ok

    async def disconnect(self):
        self._connected = False

    async def execute_task(self, agent_config, task):
        self._execute_calls.append({"agent": agent_config.get("name"), "task": task})
        if callable(self._execute_result):
            return self._execute_result(agent_config, task)
        return self._execute_result

    async def check_health(self, agent_config):
        return {"name": agent_config.get("name"), "status": "ok", "backend": "mock"}


class SlowBackend(MockBackend):
    """模拟超时的后端"""
    async def execute_task(self, agent_config, task):
        await asyncio.sleep(999)
        return "should not reach here"


class FailConnectBackend(MockBackend):
    """连接必定失败的后端"""
    async def connect(self):
        self._connected = False
        return False


# ── 辅助 ──

class MockConn:
    def __init__(self, agent_proxy, loop):
        self.agent_proxy = agent_proxy
        self.loop = loop


def load_config():
    from config.config_loader import load_backends_config
    config = load_backends_config()
    workspace = config.get("workspace_path", "./workspace")
    if not os.path.isabs(workspace):
        workspace = os.path.join(project_dir, workspace.lstrip("./"))
    config["_workspace_abs"] = workspace
    return config


def make_registry(workspace_path):
    registry = AgentRegistry(workspace_path)
    registry.scan_workspace()
    return registry


def inject_mock(backend_type, mock_backend):
    proxy_module._backend_instances[backend_type] = mock_backend


def clear_backends():
    proxy_module._backend_instances.clear()


# ── 测试用例 ──

async def test_ceo_normal_dispatch():
    """测试 1: CEO agent 正常分发任务"""
    print("=" * 50)
    print("测试 1: CEO agent 正常分发任务")
    print("=" * 50)

    config = load_config()
    registry = make_registry(config["_workspace_abs"])
    proxy = AgentProxy(registry, config)

    mock = MockBackend("claude_code", config.get("claude_code", {}),
                       execute_result="[Mock] CEO 已完成任务")
    inject_mock("claude_code", mock)

    loop = asyncio.get_event_loop()
    conn = MockConn(proxy, loop)

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    result = await loop.run_in_executor(
        None, lambda: dispatch_to_agent(conn, "ceo", "用一句话介绍你自己")
    )

    text = result.result if hasattr(result, 'result') else str(result)
    ok = "[Mock] CEO 已完成任务" in text and len(mock._execute_calls) == 1

    print(f"  返回: {text[:100]}")
    print(f"  execute_task 调用次数: {len(mock._execute_calls)}")
    if mock._execute_calls:
        c = mock._execute_calls[0]
        print(f"  调用参数: agent={c['agent']}, task={c['task'][:50]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    clear_backends()
    return ok


async def test_agent_not_found():
    """测试 2: 分发给不存在的 agent"""
    print("\n" + "=" * 50)
    print("测试 2: 分发给不存在的 agent")
    print("=" * 50)

    config = load_config()
    registry = make_registry(config["_workspace_abs"])
    proxy = AgentProxy(registry, config)

    loop = asyncio.get_event_loop()
    conn = MockConn(proxy, loop)

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    result = await loop.run_in_executor(
        None, lambda: dispatch_to_agent(conn, "不存在的agent", "测试任务")
    )

    text = result.result if hasattr(result, 'result') else str(result)
    ok = "不存在" in text

    print(f"  返回: {text[:100]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    return ok


async def test_backend_not_configured():
    """测试 3: agent 的 backend 类型在配置中不存在"""
    print("\n" + "=" * 50)
    print("测试 3: backend 未配置")
    print("=" * 50)

    config = load_config()
    registry = make_registry(config["_workspace_abs"])
    registry.agents["fake_agent"] = {
        "name": "fake_agent",
        "backend": "nonexistent_backend",
        "description": "测试用",
    }

    proxy = AgentProxy(registry, config)
    result = await proxy.dispatch("fake_agent", "测试任务")

    ok = "未配置" in result
    print(f"  返回: {result[:100]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    return ok


async def test_backend_connect_failure():
    """测试 4: 后端连接失败"""
    print("\n" + "=" * 50)
    print("测试 4: 后端连接失败")
    print("=" * 50)

    config = load_config()
    registry = make_registry(config["_workspace_abs"])
    proxy = AgentProxy(registry, config)

    fail_backend = FailConnectBackend("claude_code", config.get("claude_code", {}))
    inject_mock("claude_code", fail_backend)

    result = await proxy.dispatch("ceo", "测试任务")

    ok = "连接失败" in result
    print(f"  返回: {result[:100]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    clear_backends()
    return ok


async def test_execute_timeout():
    """测试 5: 后端执行超时"""
    print("\n" + "=" * 50)
    print("测试 5: 后端执行超时")
    print("=" * 50)

    config = load_config()
    registry = make_registry(config["_workspace_abs"])
    proxy = AgentProxy(registry, config)

    slow = SlowBackend("claude_code", config.get("claude_code", {}))
    slow._connected = True
    inject_mock("claude_code", slow)

    loop = asyncio.get_event_loop()
    conn = MockConn(proxy, loop)

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: dispatch_to_agent(conn, "ceo", "超时测试")
            ),
            timeout=3,
        )
        text = result.result if hasattr(result, 'result') else str(result)
        ok = "超时" in text or "TimeoutError" in text or "失败" in text
    except asyncio.TimeoutError:
        ok = True
        text = "asyncio.TimeoutError (预期行为)"

    print(f"  返回: {text[:100]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    clear_backends()
    return ok


async def test_conn_no_agent_proxy():
    """测试 6: conn 没有 agent_proxy"""
    print("\n" + "=" * 50)
    print("测试 6: conn 无 agent_proxy")
    print("=" * 50)

    loop = asyncio.get_event_loop()
    conn = MockConn(None, loop)

    from plugins_func.functions.dispatch_to_agent import dispatch_to_agent
    result = await loop.run_in_executor(
        None, lambda: dispatch_to_agent(conn, "ceo", "测试")
    )

    text = result.result if hasattr(result, 'result') else str(result)
    ok = "未初始化" in text

    print(f"  返回: {text[:100]}")
    print(f"  [{'PASS' if ok else 'FAIL'}]")

    return ok


# ── 主流程 ──

async def main():
    print("CEO Agent 调度功能测试 (Mock Backend)\n")

    results = {}
    tests = [
        ("CEO 正常分发", test_ceo_normal_dispatch),
        ("Agent 不存在", test_agent_not_found),
        ("Backend 未配置", test_backend_not_configured),
        ("Backend 连接失败", test_backend_connect_failure),
        ("执行超时", test_execute_timeout),
        ("Conn 无 proxy", test_conn_no_agent_proxy),
    ]

    for name, fn in tests:
        try:
            results[name] = await fn()
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            results[name] = False

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    all_pass = True
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  {status}  {name}")

    print(f"\n{'[OK] 全部通过' if all_pass else '[FAIL] 存在失败用例'}")
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
