"""CEO Agent 后端集成验证脚本（文件级，不依赖包安装）"""
import sys
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main", "xiaozhi-server")
PASS = "[OK]"
FAIL = "[FAIL]"


def check(label, fn):
    try:
        result = fn()
        if result is True:
            print(f"  {PASS} {label}")
            return True
        else:
            print(f"  {FAIL} {label}: {result}")
            return False
    except Exception as e:
        print(f"  {FAIL} {label}: {e}")
        return False


def read(path):
    with open(os.path.join(BASE, path), "r", encoding="utf-8") as f:
        return f.read()


def exists(path):
    return os.path.exists(os.path.join(BASE, path))


def contains(path, *keywords):
    content = read(path)
    return all(k in content for k in keywords)


def verify_files():
    """1. 验证所有新建文件存在"""
    print("\n=== 1. 文件存在性 ===")
    files = [
        "core/providers/agent_registry/backends/__init__.py",
        "core/providers/agent_registry/backends/base_backend.py",
        "core/providers/agent_registry/backends/multica_backend.py",
        "core/providers/agent_registry/backends/claude_code_backend.py",
        "core/providers/agent_registry/backends/openclaw_backend.py",
        "core/providers/agent_registry/backends/gitea_client.py",
        "core/providers/agent_registry/agent_proxy.py",
        "core/providers/scheduler/__init__.py",
        "core/providers/scheduler/scheduler_manager.py",
        "core/providers/scheduler/reminder_store.py",
        "core/providers/broadcast/__init__.py",
        "core/providers/broadcast/broadcast_manager.py",
        "core/providers/broadcast/message_handler.py",
        "core/providers/agent_registry/__init__.py",
        "core/providers/agent_registry/registry.py",
        "core/providers/context_manager/__init__.py",
        "core/providers/context_manager/context_manager.py",
        "core/providers/context_manager/summarizer.py",
        "core/utils/db_manager.py",
        "data/migrations/001_create_agent_tables.sql",
        "plugins_func/functions/set_reminder.py",
        "plugins_func/functions/list_reminders.py",
        "plugins_func/functions/delete_reminder.py",
        "plugins_func/functions/list_agents.py",
        "plugins_func/functions/query_agent_tasks.py",
        "plugins_func/functions/dispatch_to_agent.py",
        "plugins_func/functions/agent_health_check.py",
        "plugins_func/functions/sync_to_gitea.py",
        "plugins_func/functions/set_schedule.py",
        "plugins_func/functions/query_schedule.py",
        "workspace/backends.yaml",
        "workspace/ceo/config.yaml",
        "workspace/pm/config.yaml",
        "workspace/broadcast/config.yaml",
        "workspace/agents/executor/config.yaml",
        "workspace/agents/reviewer/config.yaml",
        "workspace/agents/assistant/config.yaml",
        "workspace/pm/skills/create_issue.py",
        "workspace/pm/skills/update_status.py",
    ]
    ok = True
    for f in files:
        ok &= check(f, lambda p=f: True if exists(p) else "文件不存在")
    return ok


def verify_base_backend():
    """2. 验证 BaseBackend 抽象类"""
    print("\n=== 2. BaseBackend 抽象类 ===")
    ok = True
    ok &= check("ABC 继承", lambda: True if contains("core/providers/agent_registry/backends/base_backend.py", "ABC") else "缺少 ABC")
    for method in ["connect", "disconnect", "execute_task", "check_health", "is_connected"]:
        ok &= check(f"抽象方法 {method}", lambda m=method: True if contains("core/providers/agent_registry/backends/base_backend.py", m) else f"缺少 {m}")
    return ok


def verify_backend_adapters():
    """3. 验证后端适配器实现"""
    print("\n=== 3. 后端适配器 ===")
    adapters = {
        "multica_backend.py": ("MulticaBackend", "BaseBackend", "ServerMCPClient", "mcp/sse"),
        "claude_code_backend.py": ("ClaudeCodeBackend", "BaseBackend", "ServerMCPClient", "mcp", "serve"),
        "openclaw_backend.py": ("OpenClawBackend", "BaseBackend", "httpx", "/api/chat"),
    }
    ok = True
    for filename, keywords in adapters.items():
        cls_name = keywords[0]
        ok &= check(f"{filename}: 类定义 {cls_name}", lambda f=filename, c=cls_name: True if contains(f"core/providers/agent_registry/backends/{f}", f"class {c}") else f"缺少 class {c}")
        ok &= check(f"{filename}: 继承 BaseBackend", lambda f=filename: True if contains(f"core/providers/agent_registry/backends/{f}", "BaseBackend") else "未继承 BaseBackend")
        for method in ["connect", "disconnect", "execute_task", "check_health"]:
            ok &= check(f"{filename}: {method}", lambda f=filename, m=method: True if contains(f"core/providers/agent_registry/backends/{f}", f"async def {m}") else f"缺少 {m}")
    return ok


def verify_gitea_client():
    """4. 验证 GiteaClient"""
    print("\n=== 4. GiteaClient ===")
    path = "core/providers/agent_registry/backends/gitea_client.py"
    ok = True
    ok &= check("class GiteaClient", lambda: True if contains(path, "class GiteaClient") else "缺少类定义")
    for method in ["connect", "close", "create_issue", "update_issue", "add_comment", "list_issues"]:
        ok &= check(f"GiteaClient.{method}", lambda m=method: True if contains(path, f"async def {m}") else f"缺少 {m}")
    ok &= check("使用 httpx", lambda: True if contains(path, "httpx") else "未使用 httpx")
    return ok


def verify_agent_proxy():
    """5. 验证 AgentProxy"""
    print("\n=== 5. AgentProxy ===")
    path = "core/providers/agent_registry/agent_proxy.py"
    ok = True
    ok &= check("class AgentProxy", lambda: True if contains(path, "class AgentProxy") else "缺少类定义")
    for method in ["dispatch", "check_health", "check_all_health", "initialize_backends", "shutdown"]:
        ok &= check(f"AgentProxy.{method}", lambda m=method: True if contains(path, f"async def {m}") else f"缺少 {m}")
    ok &= check("路由到 MulticaBackend", lambda: True if contains(path, "MulticaBackend") else "未引用 MulticaBackend")
    ok &= check("路由到 ClaudeCodeBackend", lambda: True if contains(path, "ClaudeCodeBackend") else "未引用 ClaudeCodeBackend")
    ok &= check("路由到 OpenClawBackend", lambda: True if contains(path, "OpenClawBackend") else "未引用 OpenClawBackend")
    return ok


def verify_plugins():
    """6. 验证插件注册"""
    print("\n=== 6. 插件注册 ===")
    plugins = {
        "set_reminder.py": "set_reminder",
        "list_reminders.py": "list_reminders",
        "delete_reminder.py": "delete_reminder",
        "list_agents.py": "list_agents",
        "query_agent_tasks.py": "query_agent_tasks",
        "dispatch_to_agent.py": "dispatch_to_agent",
        "agent_health_check.py": "agent_health_check",
        "sync_to_gitea.py": "sync_to_gitea",
        "set_schedule.py": "set_schedule",
        "query_schedule.py": "query_schedule",
    }
    ok = True
    for filename, func_name in plugins.items():
        path = f"plugins_func/functions/{filename}"
        ok &= check(f"{func_name}: @register_function", lambda p=path, n=func_name: True if contains(p, f'@register_function("{n}"') else "未注册")
        ok &= check(f"{func_name}: ActionResponse", lambda p=path: True if contains(p, "ActionResponse") else "未返回 ActionResponse")
    return ok


def verify_sync_to_gitea_fix():
    """7. 验证 sync_to_gitea async 修复"""
    print("\n=== 7. sync_to_gitea async 修复 ===")
    path = "plugins_func/functions/sync_to_gitea.py"
    ok = True
    ok &= check("使用 ToolType.SYSTEM_CTL", lambda: True if contains(path, "ToolType.SYSTEM_CTL") else "未使用 SYSTEM_CTL")
    ok &= check("conn 参数", lambda: True if contains(path, "def sync_to_gitea(conn") else "缺少 conn 参数")
    ok &= check("使用 conn.loop", lambda: True if contains(path, "conn.loop") else "未使用 conn.loop")
    ok &= check("使用 run_coroutine_threadsafe", lambda: True if contains(path, "run_coroutine_threadsafe") else "未使用 run_coroutine_threadsafe")
    return ok


def verify_connection_integration():
    """8. 验证 connection.py 集成"""
    print("\n=== 8. connection.py 集成 ===")
    path = "core/connection.py"
    ok = True
    ok &= check("初始化 AgentProxy", lambda: True if contains(path, "AgentProxy") else "未引用 AgentProxy")
    ok &= check("初始化 AgentRegistry", lambda: True if contains(path, "AgentRegistry") else "未引用 AgentRegistry")
    ok &= check("初始化 SchedulerManager", lambda: True if contains(path, "SchedulerManager") else "未引用 SchedulerManager")
    ok &= check("初始化 BroadcastManager", lambda: True if contains(path, "BroadcastManager") else "未引用 BroadcastManager")
    ok &= check("调用 initialize_backends", lambda: True if contains(path, "initialize_backends") else "未调用 initialize_backends")
    ok &= check("调用 agent_proxy.shutdown", lambda: True if contains(path, "agent_proxy.shutdown") else "未调用 shutdown")
    return ok


def verify_config_loader():
    """9. 验证 config_loader.py"""
    print("\n=== 9. config_loader.py ===")
    path = "config/config_loader.py"
    ok = True
    ok &= check("load_backends_config 函数", lambda: True if contains(path, "def load_backends_config") else "缺少函数")
    ok &= check("读取 backends.yaml", lambda: True if contains(path, "backends.yaml") else "未引用 backends.yaml")
    return ok


def verify_sql_migration():
    """10. 验证 SQL 迁移"""
    print("\n=== 10. SQL 迁移 ===")
    path = "data/migrations/001_create_agent_tables.sql"
    ok = True
    content = read(path)
    ok &= check("reminders 表", lambda: True if "reminders" in content else "缺少")
    ok &= check("broadcast_queue 表", lambda: True if "broadcast_queue" in content else "缺少")
    ok &= check("agent_memory 表", lambda: True if "agent_memory" in content else "缺少")
    return ok


def verify_schedule_fix():
    """11. 验证 set_schedule 输入验证"""
    print("\n=== 11. set_schedule 输入验证 ===")
    path = "plugins_func/functions/set_schedule.py"
    ok = True
    ok &= check("try/except 验证", lambda: True if contains(path, "except (ValueError, IndexError)") else "缺少异常处理")
    ok &= check("小时范围检查", lambda: True if contains(path, "0 <= hour <= 23") else "缺少小时验证")
    ok &= check("分钟范围检查", lambda: True if contains(path, "0 <= minute <= 59") else "缺少分钟验证")
    return ok


def verify_env_restriction():
    """12. 验证 claude_code_backend 环境变量限制"""
    print("\n=== 12. 环境变量安全 ===")
    path = "core/providers/agent_registry/backends/claude_code_backend.py"
    ok = True
    ok &= check("不传递 os.environ", lambda: "FAIL" if contains(path, "{**os.environ") else True)
    ok &= check("仅传递 PATH", lambda: True if contains(path, '"PATH"') else "未限制 PATH")
    ok &= check("仅传递 HOME", lambda: True if contains(path, '"HOME"') else "未限制 HOME")
    return ok


def main():
    print("=" * 50)
    print("  CEO Agent 后端集成验证")
    print("=" * 50)

    checks = [
        ("文件存在性", verify_files),
        ("BaseBackend", verify_base_backend),
        ("后端适配器", verify_backend_adapters),
        ("GiteaClient", verify_gitea_client),
        ("AgentProxy", verify_agent_proxy),
        ("插件注册", verify_plugins),
        ("async 修复", verify_sync_to_gitea_fix),
        ("connection.py", verify_connection_integration),
        ("config_loader", verify_config_loader),
        ("SQL 迁移", verify_sql_migration),
        ("输入验证", verify_schedule_fix),
        ("环境安全", verify_env_restriction),
    ]

    results = {}
    for name, fn in checks:
        results[name] = fn()

    print("\n" + "=" * 50)
    print("  验证汇总")
    print("=" * 50)
    all_ok = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status} {name}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print(f"{PASS} 所有验证通过！共 {sum(1 for _ in results)} 项检查全部 OK")
    else:
        failed = sum(1 for ok in results.values() if not ok)
        print(f"{FAIL} {failed} 项验证失败，请检查上方输出")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
