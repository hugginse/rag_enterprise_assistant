"""多会话管理与对话历史。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import login_required
from app.db import get_db
from app.models import ChatMessage, ChatSession, User
from app.schemas import (
    HistoryResponse,
    MessageListResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionPatchRequest,
    SessionResponse,
)

router = APIRouter(prefix="/api/chat", tags=["chat-sessions"])


def _session_to_response(s: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        user_id=s.user_id,
        kb_id=s.kb_id,
        title=s.title,
        created_at=s.created_at.isoformat() if s.created_at else None,
        updated_at=s.updated_at.isoformat() if s.updated_at else None,
    )


def _message_to_response(m: ChatMessage) -> MessageResponse:
    sources = m.sources or []
    return MessageResponse(
        id=m.id,
        session_id=m.session_id,
        user_id=m.user_id,
        kb_id=m.kb_id,
        question=m.question,
        answer=m.answer,
        sources=sources,
        created_at=m.created_at.isoformat() if m.created_at else None,
    )


def _get_owned_session(db: Session, session_id: int, user: User) -> ChatSession:
    s = db.get(ChatSession, session_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if s.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return s


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
    kb_id: int | None = Query(default=None),
) -> SessionListResponse:
    stmt = select(ChatSession).where(ChatSession.user_id == user.id)
    if kb_id is not None:
        stmt = stmt.where(ChatSession.kb_id == kb_id)
    stmt = stmt.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    rows = db.execute(stmt).scalars()
    return SessionListResponse(items=[_session_to_response(s) for s in rows])


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreateRequest,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> SessionResponse:
    from app.api.routes.knowledge_bases import _get_kb_or_404, _is_member

    _get_kb_or_404(db, body.kb_id)
    if not _is_member(db, body.kb_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    s = ChatSession(
        user_id=user.id,
        kb_id=body.kb_id,
        title=body.title or "新会话",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_to_response(s)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def rename_session(
    session_id: int,
    body: SessionPatchRequest,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> SessionResponse:
    s = _get_owned_session(db, session_id, user)
    s.title = body.title
    db.commit()
    db.refresh(s)
    return _session_to_response(s)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> None:
    s = _get_owned_session(db, session_id, user)
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    db.delete(s)
    db.commit()


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
def list_messages(
    session_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    _get_owned_session(db, session_id, user)
    rows = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
    ).scalars()
    return MessageListResponse(items=[_message_to_response(m) for m in rows])


@router.get("/history", response_model=HistoryResponse)
def history(
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(default=None),
) -> HistoryResponse:
    """分页历史；admin 可按 user_id 过滤查看全部，默认自己。"""
    if user.role == "admin":
        base = select(ChatMessage)
        count_base = select(func.count()).select_from(ChatMessage)
        if user_id is not None:
            base = base.where(ChatMessage.user_id == user_id)
            count_base = count_base.where(ChatMessage.user_id == user_id)
    else:
        base = select(ChatMessage).where(ChatMessage.user_id == user.id)
        count_base = (
            select(func.count()).select_from(ChatMessage).where(ChatMessage.user_id == user.id)
        )

    total = db.scalar(count_base) or 0
    rows = db.execute(
        base.order_by(ChatMessage.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars()
    return HistoryResponse(
        total=total,
        items=[_message_to_response(m) for m in rows],
    )
