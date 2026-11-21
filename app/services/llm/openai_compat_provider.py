"""OpenAI 兼容 API Provider（任意兼容端点，示例为 OpenAI 官方）。"""

from collections.abc import Iterator

from openai import OpenAI

from app.core.config import settings
from app.services.llm.base import RAG_SYSTEM_PROMPT


class OpenAICompatProvider:
    def __init__(self) -> None:
        self._client = OpenAI(
            base_url=settings.openai_compat_base_url,
            api_key=settings.openai_compat_api_key or "empty",
        )
        self._embed_model = settings.openai_compat_model  # 对话模型
        # 嵌入单独配置时可扩展；默认尝试 text-embedding-3-small
        self._embedding_model = getattr(
            settings, "openai_compat_embed_model", "text-embedding-3-small"
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._embedding_model, input=texts)
        # 按 index 排序保证顺序
        data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in data]

    def chat_stream(self, system: str, question: str, context: str) -> Iterator[tuple[str, str]]:
        prompt = f"参考资料：\n{context}\n\n问题：{question}"
        stream = self._client.chat.completions.create(
            model=settings.openai_compat_model,
            messages=[
                {"role": "system", "content": system or RAG_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta is None:
                continue
            # 部分兼容端点将思考放在 reasoning_content
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield ("thinking", reasoning)
            content = getattr(delta, "content", None)
            if content:
                yield ("delta", content)
