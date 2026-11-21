"""FastAPI 应用工厂。"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, chat_sessions, documents, knowledge_bases, stats, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """startup：清理遗留 pending/processing 死状态。"""
    from app.db import SessionLocal
    from app.services.ingest import cleanup_dead_documents

    db = SessionLocal()
    try:
        n = cleanup_dead_documents(db)
        if n:
            logger.info("startup: marked %s dead documents as failed", n)
    except Exception:
        logger.exception("startup cleanup failed")
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="rag_enterprise_assistant",
        description="企业级知识库问答系统（RAG）",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 本地前端分端口联调（如 5173）；M3 #9 同源挂载后可收紧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(knowledge_bases.router)
    app.include_router(documents.router)
    app.include_router(stats.router)
    app.include_router(chat.router)
    app.include_router(chat_sessions.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
