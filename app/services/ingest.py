"""文档异步入库编排：pending → processing → completed | failed。"""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document
from app.services.chunker import chunk_text
from app.services.llm import create_provider
from app.services.parser import ParseError, parse_file
from app.services.vector import add_chunks, delete_doc

logger = logging.getLogger(__name__)


def ingest_document_by_id(doc_id: int) -> None:
    """BackgroundTasks 入口：独立 session 执行解析→分块→向量化→状态机。"""
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        _run(session, doc_id)
    finally:
        session.close()


def _run(db: Session, doc_id: int) -> None:
    doc = db.get(Document, doc_id)
    if doc is None or doc.status == "completed":
        return

    doc.status = "processing"
    doc.error_msg = None
    db.commit()

    path = Path(settings.upload_dir) / doc.stored_name
    try:
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {doc.stored_name}")

        text = parse_file(path)
        chunks = chunk_text(text)
        if not chunks:
            raise ParseError("分块结果为空")

        provider = create_provider()
        try:
            embeddings = provider.embed(chunks)
        except Exception as exc:
            msg = str(exc) or exc.__class__.__name__
            lowered = msg.lower()
            if any(k in lowered for k in ("connect", "refused", "11434", "unreachable")):
                raise RuntimeError("无法连接 Ollama") from exc
            raise

        delete_doc(doc.kb_id, doc.id)
        add_chunks(
            kb_id=doc.kb_id,
            doc_id=doc.id,
            file_name=doc.filename,
            chunks=chunks,
            embeddings=embeddings,
        )

        doc.chunk_count = len(chunks)
        doc.status = "completed"
        doc.error_msg = None
        db.commit()
        logger.info("doc %s completed, chunks=%s", doc_id, len(chunks))
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "failed"
            doc.error_msg = str(exc) or exc.__class__.__name__
            db.commit()
        logger.exception("doc %s failed", doc_id)


def cleanup_dead_documents(db: Session) -> int:
    """启动时把遗留 pending/processing 置 failed。"""
    rows = (
        db.execute(select(Document).where(Document.status.in_(("pending", "processing"))))
        .scalars()
        .all()
    )
    for doc in rows:
        doc.status = "failed"
        doc.error_msg = "服务重启导致任务中断，请重新上传"
    if rows:
        db.commit()
    return len(rows)
