"""FastAPI 应用工厂。"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, chat, chat_sessions, documents, knowledge_bases, stats, users

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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


class NoCacheStaticFiles(StaticFiles):
    """静态资源一律 no-cache，便于开发与部署后立即生效。"""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="rag_enterprise_assistant",
        description="企业级知识库问答系统（RAG）",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 开发期分端口联调（5173）保留；同源 8000 访问不依赖 CORS
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

    # 静态资源：/static/* → static/ 目录，no-cache
    app.mount(
        "/static",
        NoCacheStaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """SPA 入口；hash 路由无需其它 fallback。"""
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
