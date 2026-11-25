"""监控 context 长度，触发压缩或滑动窗口"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class ContextManager:
    def __init__(self, model_context_window: int = 200000):
        self.threshold = int(model_context_window * 0.5)
        self.max_window = int(model_context_window * 0.75)

    def check_and_compress(self, messages: list, llm=None) -> list:
        total_tokens = self._estimate_tokens(messages)
        if total_tokens < self.threshold:
            return messages

        logger.bind(tag=TAG).info(f"上下文接近阈值: {total_tokens}/{self.threshold}, 开始压缩")

        # 阶段一：滑动窗口
        windowed = self._sliding_window_with_memory(messages)
        if self._estimate_tokens(windowed) < self.max_window:
            return windowed

        # 阶段二：LLM 摘要压缩
        if llm:
            from .summarizer import Summarizer
            summarizer = Summarizer(llm)
            old_messages = windowed[:-10]
            recent_messages = windowed[-10:]
            summary = summarizer.compress(old_messages)
            return [{"role": "system", "content": f"历史摘要: {summary}"}] + recent_messages

        return windowed

    def _sliding_window_with_memory(self, messages: list, keep_count: int = 20) -> list:
        if len(messages) <= keep_count:
            return messages
        return messages[-keep_count:]

    def _estimate_tokens(self, messages: list) -> int:
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return int(total_chars * 1.5)
