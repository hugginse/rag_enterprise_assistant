"""文档上传、列表与删除：落盘→建 pending→立即返回→后台向量化。"""

import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.knowledge_bases import _get_kb_or_404, _is_member
from app.core.config import settings
from app.core.security import admin_required, login_required
from app.db import get_db
from app.models import Document, User
from app.schemas import DocumentListResponse, DocumentResponse
from app.services.ingest import ingest_document_by_id

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {".txt", ".md", ".pdf", ".docx"}
MIME_BY_EXT = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        kb_id=doc.kb_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        error_msg=doc.error_msg,
        chunk_count=doc.chunk_count,
        created_by=doc.created_by,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
    )


def _get_doc_or_404(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return doc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    kb_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    _get_kb_or_404(db, kb_id)
    if not _is_member(db, kb_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    docs = db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.id.desc())
    ).scalars()
    return DocumentListResponse(items=[_doc_to_response(d) for d in docs])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    kb_id: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    _get_kb_or_404(db, int(kb_id))

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 txt/md/pdf/docx 格式",
        )

    content = await file.read()
    max_bytes = settings.upload_max_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件超过 {settings.upload_max_mb}MB 限制",
        )
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / stored_name
    dest.write_bytes(content)

    doc = Document(
        kb_id=int(kb_id),
        filename=filename,
        stored_name=stored_name,
        file_type=ext.lstrip("."),
        file_size=len(content),
        status="pending",
        chunk_count=0,
        created_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 立即返回 pending，后台处理
    background_tasks.add_task(ingest_document_by_id, doc.id)
    return _doc_to_response(doc)


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    doc = _get_doc_or_404(db, doc_id)
    if not _is_member(db, doc.kb_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return _doc_to_response(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: int,
    user: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> None:
    doc = _get_doc_or_404(db, doc_id)
    stored_name = doc.stored_name
    kb_id = doc.kb_id
    try:
        db.execute(delete(Document).where(Document.id == doc_id))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="删除文档失败") from None

    path = Path(settings.upload_dir) / stored_name
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass

    # Chroma 分块清理
    try:
        from app.services.vector import delete_doc

        delete_doc(kb_id, doc_id)
    except Exception:
        pass
