"""调用 LLM 压缩对话历史为摘要"""
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class Summarizer:
    def __init__(self, llm):
        self.llm = llm

    def compress(self, messages: list) -> str:
        conversation = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages
        )
        prompt = f"请将以下对话压缩为简洁的摘要，保留关键信息（任务、决策、时间点）：\n\n{conversation}"
        try:
            summary = self.llm.response_no_stream(system_prompt=prompt, user_prompt="生成摘要")
            logger.bind(tag=TAG).info(f"摘要压缩完成，原 {len(messages)} 条消息")
            return summary
        except Exception as e:
            logger.bind(tag=TAG).error(f"摘要压缩失败: {e}")
            return f"[压缩失败: {len(messages)} 条消息]"
