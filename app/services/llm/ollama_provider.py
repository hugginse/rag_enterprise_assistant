"""本地 Ollama Provider（qwen3:4b / qwen3-embedding:4b）。"""

from collections.abc import Iterator

import ollama

from app.core.config import settings
from app.services.llm.base import RAG_SYSTEM_PROMPT


class OllamaProvider:
    def __init__(self) -> None:
        self._client = ollama.Client(host=settings.ollama_base_url)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # 嵌入侧固定 4096 上下文（见 architecture §4）
        resp = self._client.embed(
            model=settings.ollama_embed_model,
            input=texts,
            options={"num_ctx": 4096},
        )
        return list(resp["embeddings"])

    def chat_stream(self, system: str, question: str, context: str) -> Iterator[tuple[str, str]]:
        prompt = f"参考资料：\n{context}\n\n问题：{question}"
        stream = self._client.chat(
            model=settings.ollama_llm_model,
            messages=[
                {"role": "system", "content": system or RAG_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            think=settings.ollama_think,
            options={"num_ctx": settings.ollama_num_ctx},
        )
        for chunk in stream:
            message = chunk.get("message") or {}
            thinking = message.get("thinking")
            if thinking:
                yield ("thinking", thinking)
            content = message.get("content")
            if content:
                yield ("delta", content)
