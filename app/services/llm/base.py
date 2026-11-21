"""LLM Provider 抽象与工厂。"""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

RAG_SYSTEM_PROMPT = (
    "你是企业知识库问答助手。请严格依据提供的参考资料回答问题：\n"
    "1. 仅使用参考资料中的信息作答，不要编造；\n"
    "2. 参考资料不足以回答时，如实说明「未找到相关内容」，不要猜测；\n"
    "3. 使用中文，回答简洁、专业；\n"
    "4. 可适当引用资料中的文件名以便溯源。"
)


@runtime_checkable
class LLMProvider(Protocol):
    """嵌入与流式对话协议。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本转向量。"""
        ...

    def chat_stream(self, system: str, question: str, context: str) -> Iterator[tuple[str, str]]:
        """逐 token 产出 ('thinking'|'delta', text) 元组。"""
        ...


def create_provider() -> LLMProvider:
    """按 LLM_PROVIDER 配置实例化 Provider。"""
    from app.core.config import settings

    if settings.llm_provider == "openai_compat":
        from app.services.llm.openai_compat_provider import OpenAICompatProvider

        return OpenAICompatProvider()
    from app.services.llm.ollama_provider import OllamaProvider

    return OllamaProvider()
