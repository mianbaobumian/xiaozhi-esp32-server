"""Gitea issue 同步插件 — 创建/更新/查询 issue"""
from plugins_func.register import register_function, ToolType, ActionResponse, Action

sync_to_gitea_desc = {
    "type": "function",
    "function": {
        "name": "sync_to_gitea",
        "description": "同步任务到 Gitea Issues。支持创建、更新、查询 issue。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: create / update / list",
                    "enum": ["create", "update", "list"],
                },
                "title": {
                    "type": "string",
                    "description": "Issue 标题（create 时必填）",
                },
                "body": {
                    "type": "string",
                    "description": "Issue 内容（create 时可选）",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "Issue 编号（update 时必填）",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
                "state": {
                    "type": "string",
                    "description": "Issue 状态（update 时可选）: open / closed",
                },
            },
            "required": ["action"],
        },
    },
}


@register_function("sync_to_gitea", sync_to_gitea_desc, ToolType.WAIT)
def sync_to_gitea(action: str, title: str = "", body: str = "",
                  issue_number: int = None, labels: list = None, state: str = None):
    import asyncio
    from config.config_loader import load_backends_config
    from core.providers.agent_registry.backends.gitea_client import GiteaClient

    config = load_backends_config()
    gitea_config = config.get("gitea", {})
    client = GiteaClient(gitea_config)

    async def _run():
        await client.connect()
        try:
            if action == "create":
                if not title:
                    return "创建 issue 需要 title 参数"
                result = await client.create_issue(title, body, labels)
                if "error" in result:
                    return f"创建失败: {result['error']}"
                return f"Issue #{result['number']} 已创建: {result['title']}"

            elif action == "update":
                if not issue_number:
                    return "更新 issue 需要 issue_number 参数"
                kwargs = {}
                if title:
                    kwargs["title"] = title
                if body:
                    kwargs["body"] = body
                if state:
                    kwargs["state"] = state
                if labels:
                    kwargs["labels"] = [{"name": l} for l in labels]
                result = await client.update_issue(issue_number, **kwargs)
                if "error" in result:
                    return f"更新失败: {result['error']}"
                return f"Issue #{issue_number} 已更新"

            elif action == "list":
                issues = await client.list_issues(state or "open")
                if not issues:
                    return "当前没有 issue"
                lines = []
                for i in issues[:10]:
                    label_str = ", ".join(l["name"] for l in i.get("labels", []))
                    lines.append(f"- #{i['number']} [{i['state']}] {i['title']}"
                                 + (f" ({label_str})" if label_str else ""))
                return "Gitea Issues:\n" + "\n".join(lines)

            else:
                return f"未知操作: {action}"
        finally:
            await client.close()

    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_run())
    except RuntimeError:
        result = asyncio.run(_run())

    return ActionResponse(Action.REQLLM, result, None)
