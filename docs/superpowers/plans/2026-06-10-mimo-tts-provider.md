# MiMo TTS Provider 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 MiMo-V2.5-TTS 语音合成 provider，支持预置音色、风格控制。

**Tech Stack:** Python 3.10, requests, base64

**设计文档:** `docs/superpowers/specs/2026-06-10-mimo-tts-provider-design.md`

---

## 文件结构

### 新建文件

| 路径 | 职责 |
|------|------|
| `main/xiaozhi-server/core/providers/tts/mimo.py` | MiMo TTS Provider |

### 修改文件

无（数据库迁移已由用户完成）

---

## Task 1: 实现 MiMo TTS Provider

**Files:**
- Create: `main/xiaozhi-server/core/providers/tts/mimo.py`

**Context:** MiMo TTS API 与 OpenAI TTS 完全不兼容。端点为 `/v1/chat/completions`，认证用 `api-key` 头，目标文本放 `role: assistant`，风格指令放 `role: user`，响应为 JSON 中 `choices[0].message.audio.data` 的 base64 编码音频。

参考 `core/providers/tts/openai.py` 的结构，但 `text_to_speak` 实现完全不同。

- [ ] **Step 1: 创建 mimo.py**

```python
# main/xiaozhi-server/core/providers/tts/mimo.py
"""MiMo-V2.5-TTS 语音合成 Provider"""
import base64
import requests
from core.utils.util import check_model_key
from core.providers.tts.base import TTSProviderBase
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    TTS_PARAM_CONFIG = [
        ("ttsRate", "speed", 0.25, 4, 1, lambda v: round(float(v), 2)),
    ]

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://api.xiaomimimo.com/v1").rstrip("/")
        self.model = config.get("model", "mimo-v2.5-tts")
        if config.get("private_voice"):
            self.voice = config.get("private_voice")
        else:
            self.voice = config.get("voice", "冰糖")
        self.audio_file_type = config.get("format", "wav")
        self.style = config.get("style", "")

        speed = config.get("speed", "1.0")
        self.speed = float(speed) if speed else 1.0

        self._apply_percentage_params(config)

        self.output_file = config.get("output_dir", "tmp/")
        model_key_msg = check_model_key("TTS", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

    async def text_to_speak(self, text, output_file):
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        messages = []
        if self.style:
            messages.append({"role": "user", "content": self.style})
        messages.append({"role": "assistant", "content": text})

        data = {
            "model": self.model,
            "messages": messages,
            "audio": {
                "format": self.audio_file_type,
                "voice": self.voice,
            },
        }

        api_url = f"{self.base_url}/chat/completions"
        response = requests.post(api_url, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(
                f"MiMo TTS请求失败: {response.status_code} - {response.text}"
            )

        resp_json = response.json()
        try:
            audio_b64 = resp_json["choices"][0]["message"]["audio"]["data"]
        except (KeyError, IndexError) as e:
            raise Exception(f"MiMo TTS响应格式异常: {e}, response={resp_json}")

        audio_bytes = base64.b64decode(audio_b64)

        if output_file:
            with open(output_file, "wb") as audio_file:
                audio_file.write(audio_bytes)
        else:
            return audio_bytes
```

- [ ] **Step 2: Commit**

```bash
git add main/xiaozhi-server/core/providers/tts/mimo.py
git commit -m "feat: implement MiMo-V2.5-TTS provider"
```

---

## 验证清单

- [ ] mimo.py 文件存在且可被动态加载（`core.providers.tts.mimo`）
- [ ] `TTSProvider` 类继承 `TTSProviderBase`
- [ ] `text_to_speak` 正确构造 MiMo API 请求（api-key 头、messages 格式）
- [ ] `text_to_speak` 正确解析 base64 音频响应
- [ ] style 非空时添加 role: user 消息，为空时不添加
- [ ] 配置字段与数据库 ai_model_config JSON 一致（api_key, base_url, model, voice, format, style）
- [ ] base_url 支持用户自定义（rstrip 处理尾部斜杠）
