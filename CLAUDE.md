# xiaozhi-esp32-server
# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
小智 ESP32 AI 智能硬件服务端，包含管理后台和 AI 服务器。

## 项目结构

```
xiaozhi-esp32-server/
├── main/
│   ├── manager-api/       # Java Spring Boot 后台 API
│   ├── manager-web/       # Vue 2 管理后台 Web 前端
│   ├── manager-mobile/    # UniApp 移动端管理后台
│   └── xiaozhi-server/    # Python AI 服务器（核心）
├── docs/                  # 文档和图片
└── docker-setup.sh        # Docker 部署脚本
```

## 子项目技术栈

### manager-api（后台 API）
- **语言**: Java 21
- **框架**: Spring Boot 3.4.3
- **构建**: Maven
- **包结构**: `xiaozhi.modules.{agent, config, correctword, device, ...}`
- **启动**: `mvn spring-boot:run` 或运行 `Application.java`

### manager-web（Web 管理后台）
- **框架**: Vue 2 + Element UI
- **构建**: Vue CLI
- **启动**: `npm run serve`
- **打包**: `npm run build`

### manager-mobile（移动端管理后台）
- **框架**: UniApp (Vue 3 + TypeScript)
- **包管理**: pnpm
- **启动**: 参考 UniApp 开发文档

### xiaozhi-server（AI 服务器 - 核心）
- **语言**: Python 3.10
- **核心模块**:
  - `core/providers/asr/` — 语音识别（ASR）
  - `core/providers/vad/` — 语音活动检测（VAD）
  - `core/providers/llm/` — 大语言模型（LLM）
  - `core/providers/vllm/` — 视觉大语言模型（VLLM）
  - `core/providers/tts/` — 语音合成（TTS）
  - `core/providers/intent/` — 意图识别
  - `core/providers/memory/` — 记忆管理
  - `core/providers/tools/` — 工具调用
- **入口**: `core/websocket_server.py`（WebSocket）、`core/http_server.py`（HTTP）
- **配置**: `config/config.yaml`
- **依赖安装**: `pip install -r requirements.txt`

## 开发注意事项

- Python 环境推荐 3.10，依赖版本见 `requirements.txt`
- Java 需要 JDK 21+
- manager-web 使用 Vue 2（不是 Vue 3）
- manager-mobile 使用 pnpm 管理依赖
- 配置文件在 `main/xiaozhi-server/config/` 下
- `.claude` 和 `.codegraph` 目录已被 gitignore，不提交到仓库
