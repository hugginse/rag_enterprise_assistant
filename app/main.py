"""FastAPI 应用工厂。"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="rag_enterprise_assistant",
        description="企业级知识库问答系统（RAG）",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
