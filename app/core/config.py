"""Pydantic Settings 应用配置。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """环境变量配置（见 docs/architecture.md §4）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 安全
    secret_key: str = "dev-secret-key-change-me"
    jwt_expire_hours: int = 24

    # 数据库
    database_url: str = "postgresql+psycopg2://rag:rag123@localhost:5432/rag_enterprise"

    # LLM 双模
    llm_provider: str = "ollama"  # ollama | openai_compat
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen3:4b"
    ollama_embed_model: str = "qwen3-embedding:4b"
    ollama_think: bool = True
    ollama_num_ctx: int = 8192

    openai_compat_base_url: str = "https://api.openai.com/v1"
    openai_compat_api_key: str = ""
    openai_compat_model: str = "gpt-4o-mini"

    # 检索与分块
    retrieval_top_k: int = 4
    retrieval_score_threshold: float = 0.3
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 存储
    chroma_persist_dir: str = "chroma_data"
    upload_dir: str = "uploads"
    upload_max_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
