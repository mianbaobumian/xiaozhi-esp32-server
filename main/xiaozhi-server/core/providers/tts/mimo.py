# main/xiaozhi-server/core/providers/tts/mimo.py
"""MiMo-V2.5-TTS 语音合成 Provider"""
import os
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

        # 音色克隆：非空时自动切换到 voiceclone 模式
        self.voice_clone_audio = config.get("voice_clone_audio", "")
        if self.voice_clone_audio and os.path.exists(self.voice_clone_audio):
            self.model = "mimo-v2.5-tts-voiceclone"
            logger.bind(tag=TAG).info(f"启用音色克隆模式, 参考音频: {self.voice_clone_audio}")

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

        # 音色克隆：读取参考音频并构造 data URI
        voice = self.voice
        if self.voice_clone_audio and os.path.exists(self.voice_clone_audio):
            with open(self.voice_clone_audio, "rb") as f:
                clone_b64 = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(self.voice_clone_audio)[1].lower()
            mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            voice = f"data:{mime};base64,{clone_b64}"

        data = {
            "model": self.model,
            "messages": messages,
            "audio": {
                "format": self.audio_file_type,
                "voice": voice,
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
