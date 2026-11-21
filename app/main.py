"""FastAPI 应用工厂。"""

from fastapi import FastAPI

from app.api.routes import auth, users


def create_app() -> FastAPI:
    app = FastAPI(
        title="rag_enterprise_assistant",
        description="企业级知识库问答系统（RAG）",
        version="0.1.0",
    )

    app.include_router(auth.router)
    app.include_router(users.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
