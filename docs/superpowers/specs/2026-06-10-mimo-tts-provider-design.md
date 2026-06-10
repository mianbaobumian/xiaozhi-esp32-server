# MiMo TTS Provider 设计文档

> 日期: 2026-06-10
> 状态: Draft

## 1. 概述

为 xiaozhi-esp32-server 新增 MiMo-V2.5-TTS 语音合成 provider，支持小米 MiMo TTS API 的预置音色、音色设计、音色克隆三种模型。

MiMo TTS 的 API 与现有 OpenAI TTS 完全不兼容（端点、认证、请求体、响应格式均不同），需要独立实现。

## 2. API 差异对比

| 对比项 | 现有 openai.py | MiMo TTS |
|--------|---------------|----------|
| 端点 | /v1/audio/speech | /v1/chat/completions |
| 认证头 | Authorization: Bearer xxx | api-key: xxx |
| 请求体 | {"input": text, "voice": "alloy"} | {"messages": [...], "audio": {"voice": "冰糖"}} |
| 响应 | 直接返回音频二进制 | JSON: choices[0].message.audio.data (base64) |
| 风格控制 | 无 | role: user 消息传风格指令 |
| 目标文本位置 | input 字段 | role: assistant 消息 |

## 3. 架构

### 3.1 文件结构

```
新建文件:
  main/xiaozhi-server/core/providers/tts/mimo.py    # TTS Provider 实现

修改文件:
  无（数据库迁移已由用户完成）
```

### 3.2 类设计

```python
class TTSProvider(TTSProviderBase):
    TTS_PARAM_CONFIG = [
        ("ttsRate", "speed", 0.25, 4, 1, lambda v: round(float(v), 2)),
    ]

    def __init__(self, config, delete_audio_file):
        # 从 config 读取字段（对应数据库 ai_model_config 的 JSON）
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://api.xiaomimimo.com/v1")
        self.model = config.get("model", "mimo-v2.5-tts")
        self.voice = config.get("voice", "冰糖")
        self.audio_file_type = config.get("format", "wav")
        self.style = config.get("style", "")

    async def text_to_speak(self, text, output_file):
        # 构造 MiMo chat/completions 请求
        # base64 解码音频响应
        # 写入文件或返回 bytes
```

### 3.3 继承关系

```
TTSProviderBase (ABC)
  └── TTSProvider (mimo.py)
        - text_to_speak() 实现 MiMo API 调用
        - 继承基类的重试、流式分段、opus 编码等能力
```

## 4. 数据流

### 4.1 非流式 TTS 调用

```
text_to_speak(text, output_file)
  │
  ├─ 构造 messages:
  │    ├─ {"role": "user", "content": self.style}     ← style 非空时才加
  │    └─ {"role": "assistant", "content": text}       ← 目标文本（必须）
  │
  ├─ POST {base_url}/chat/completions
  │    Headers:
  │      api-key: {api_key}
  │      Content-Type: application/json
  │    Body:
  │      {
  │        "model": self.model,
  │        "messages": [...],
  │        "audio": {"format": self.audio_file_type, "voice": self.voice}
  │      }
  │
  ├─ 响应解析:
  │    response.json()["choices"][0]["message"]["audio"]["data"]
  │    → base64.b64decode() → audio_bytes
  │
  └─ 输出:
       ├─ output_file 非空 → 写入文件
       └─ output_file 为空 → 返回 audio_bytes
```

### 4.2 与基类的交互

基类 `TTSProviderBase` 的 `to_tts()` 和 `to_tts_stream()` 方法会：
1. 清理 Markdown
2. 应用替换词（correct_words）
3. 调用 `text_to_speak(text, output_file)` — 这是子类唯一需要实现的方法
4. 处理重试（最多 5 次）
5. 将音频转为 opus 编码推送到设备

MiMo provider 只需实现 `text_to_speak()`，其余由基类处理。

## 5. 配置

### 5.1 数据库配置（已由用户完成）

`ai_model_config` 表中的 JSON 配置：

```json
{
  "type": "mimo",
  "api_key": "",
  "base_url": "https://api.xiaomimimo.com/v1",
  "output_dir": "tmp/",
  "model": "mimo-v2.5-tts",
  "voice": "冰糖",
  "format": "wav",
  "style": "",
  "voice_clone_audio": ""
}
```

### 5.2 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| type | string | mimo | provider 类型，对应文件名 |
| api_key | string | (必填) | MiMo API 密钥 |
| base_url | string | https://api.xiaomimimo.com/v1 | API 基础地址 |
| output_dir | string | tmp/ | 音频临时文件目录 |
| model | string | mimo-v2.5-tts | 模型 ID |
| voice | string | 冰糖 | 预置音色 ID |
| format | string | wav | 音频格式（非流式用 wav） |
| style | string | (空) | 风格指令，放 role: user 消息 |
| voice_clone_audio | string | (空) | 克隆参考音频文件路径，非空时自动启用 voiceclone 模式 |

### 5.3 模型选项

| Model ID | 功能 | 适用场景 |
|----------|------|----------|
| mimo-v2.5-tts | 预置音色 | 日常语音播报（推荐） |
| mimo-v2.5-tts-voicedesign | 音色设计 | 需要自定义音色 |
| mimo-v2.5-tts-voiceclone | 音色克隆 | 用参考音频克隆 |

### 5.4 预置音色

| Voice ID | 语言 | 性别 |
|----------|------|------|
| 冰糖 | 中文 | 女 |
| 茉莉 | 中文 | 女 |
| 苏打 | 中文 | 男 |
| 白桦 | 中文 | 男 |
| Mia | 英文 | 女 |
| Chloe | 英文 | 女 |
| Milo | 英文 | 男 |
| Dean | 英文 | 男 |

## 6. 风格控制

### 6.1 实现方式

风格通过 `config.style` 字段配置，作为 `role: user` 消息发送：

```python
messages = []
if self.style:
    messages.append({"role": "user", "content": self.style})
messages.append({"role": "assistant", "content": text})
```

### 6.2 风格示例

```yaml
# config 中的 style 字段
style: "用温柔慵懒的语调，像在深夜电台里讲故事"
style: "播报新闻，严肃专业的语气"
style: "活泼欢快，像在和朋友聊天"
style: ""  # 空 = 不传 user 消息，使用默认风格
```

### 6.3 音频标签控制

除 config 中的固定风格外，用户还可以在待合成文本中嵌入音频标签：

```
（紧张，深呼吸）呼……冷静，冷静。
```

音频标签直接写在 `role: assistant` 的文本中，MiMo 会自动识别。

## 7. 音色克隆

### 7.1 配置驱动

通过 `voice_clone_audio` 配置字段指定参考音频文件路径。非空时自动切换到 voiceclone 模式：

```
voice_clone_audio 非空:
  → model 强制为 "mimo-v2.5-tts-voiceclone"
  → 读取音频文件 → base64 编码 → 构造 data URI
  → voice = "data:{mime};base64,{b64}"

voice_clone_audio 为空:
  → model 保持用户配置
  → voice 使用预置音色 ID
```

### 7.2 MIME 类型判断

根据文件扩展名自动判断：

| 扩展名 | MIME 类型 |
|--------|-----------|
| .mp3 | audio/mpeg |
| .wav | audio/wav |
| 其他 | audio/wav（默认） |

### 7.3 约束

- 参考音频 base64 后不超过 10MB
- 仅支持 mp3/wav 格式
- 设置 voice_clone_audio 后，voice 配置字段被忽略

## 8. 错误处理

| 场景 | 处理方式 |
|------|----------|
| HTTP 非 200 | raise Exception，基类重试机制接管 |
| 响应 JSON 缺少 audio 字段 | raise Exception，基类重试 |
| base64 解码失败 | raise Exception，基类重试 |
| api_key 为空 | check_model_key() 在 __init__ 时告警 |
| 网络超时 | requests 默认超时，基类重试 |

## 9. 约束

- 当前仅实现非流式（wav），MiMo 流式为兼容模式暂不支持
- 音色克隆的 base64 音频不超过 10MB
- 流式上线后需新增 pcm16 流式支持（不在本次范围内）
