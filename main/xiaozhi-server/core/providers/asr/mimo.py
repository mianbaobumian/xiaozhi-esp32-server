import os
import json
import base64
import time
from typing import Optional, Tuple, List

import requests

from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()

# MiMo 语音识别单次请求的 base64 音频上限（官方限制 10MB）
MIMO_MAX_BASE64_SIZE = 10 * 1024 * 1024


class ASRProvider(ASRProviderBase):
    """小米 MiMo-V2.5-ASR 语音识别适配器

    MiMo 的语音识别不是 OpenAI Whisper 的 /v1/audio/transcriptions（multipart
    上传文件），而是 OpenAI Chat Completions 风格：
      1. 音频转 Base64，按 data URL（data:audio/wav;base64,xxx）放进 messages；
      2. POST {base_url}/chat/completions，请求头 api-key: <key>；
      3. 识别文本从 choices[0].message.content 返回。

    因此 base_url 只需要填到 /v1 这一级，例如：
      https://api.xiaomimimo.com/v1
      https://token-plan-cn.xiaomimimo.com/v1
    """

    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        # 音频文件上传类型，整段识别后返回文本
        self.interface_type = InterfaceType.NON_STREAM

        self.api_key = config.get("api_key")
        base_url = (config.get("base_url") or "https://api.xiaomimimo.com/v1").rstrip(
            "/"
        )
        # 兼容两种写法：只写到 /v1，或直接写到 /v1/chat/completions
        if base_url.endswith("/chat/completions"):
            self.api_url = base_url
        elif base_url.endswith("/v1"):
            self.api_url = f"{base_url}/chat/completions"
        else:
            self.api_url = f"{base_url}/v1/chat/completions"

        self.model = config.get("model_name") or config.get("model") or "mimo-v2.5-asr"
        # auto 自动检测；zh / en 手动指定
        self.language = config.get("language") or "auto"
        self.enable_lid = config.get("enable_lid", True)
        self.enable_itn = config.get("enable_itn", True)
        self.timeout = int(config.get("timeout", 30))
        self.output_dir = config.get("output_dir", "tmp/")
        self.delete_audio_file = delete_audio_file

        os.makedirs(self.output_dir, exist_ok=True)

        model_key_msg = check_model_key("ASR", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

    def requires_file(self) -> bool:
        return True

    def prefers_temp_file(self) -> bool:
        return True

    def _build_payload(self, audio_base64: str) -> dict:
        asr_options = {
            "enable_lid": self.enable_lid,
            "enable_itn": self.enable_itn,
        }
        if self.language:
            asr_options["language"] = self.language
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:audio/wav;base64,{audio_base64}"
                            },
                        }
                    ],
                }
            ],
            "asr_options": asr_options,
        }

    @staticmethod
    def _extract_text(data: dict) -> str:
        """从 chat.completions 响应里取出识别文本"""
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: List[str] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                return "".join(parts).strip()
        # 兜底：部分实现会把文本放在顶层字段
        for key in ("text", "result", "transcription"):
            value = data.get(key)
            if isinstance(value, str):
                return value.strip()
        return ""

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, artifacts=None
    ) -> Tuple[Optional[str], Optional[str]]:
        file_path = None
        try:
            if artifacts is None:
                return "", None
            file_path = artifacts.file_path
            wav_path = artifacts.temp_path or artifacts.file_path
            if not wav_path or not os.path.exists(wav_path):
                raise ValueError("缺少可用的 wav 音频文件")

            with open(wav_path, "rb") as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode("utf-8")

            if len(audio_base64) > MIMO_MAX_BASE64_SIZE:
                raise ValueError(
                    f"音频过大，Base64 后 {len(audio_base64) / 1024 / 1024:.1f}MB，"
                    "MiMo 限制 10MB"
                )

            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
            }

            start_time = time.time()
            response = requests.post(
                self.api_url,
                data=json.dumps(
                    self._build_payload(audio_base64), ensure_ascii=False
                ).encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
            )
            logger.bind(tag=TAG).debug(
                f"语音识别耗时: {time.time() - start_time:.3f}s | "
                f"状态: {response.status_code} | 结果: {response.text[:500]}"
            )

            if response.status_code != 200:
                raise Exception(
                    f"API请求失败: {response.status_code} - {response.text[:500]}"
                )

            text = self._extract_text(response.json())
            return text, file_path

        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}")
            return "", file_path