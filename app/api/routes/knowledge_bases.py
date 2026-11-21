"""知识库 CRUD 与成员授权。"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import admin_required, login_required
from app.db import get_db
from app.models import ChatMessage, ChatSession, Document, KbMember, KnowledgeBase, User
from app.schemas import (
    KbCreateRequest,
    KbListResponse,
    KbMemberAddRequest,
    KbMemberResponse,
    KbResponse,
    KbUpdateRequest,
)

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


def _kb_to_response(kb: KnowledgeBase) -> KbResponse:
    return KbResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_by=kb.created_by,
        status=kb.status,
        created_at=kb.created_at.isoformat() if kb.created_at else None,
    )


def _is_member(db: Session, kb_id: int, user: User) -> bool:
    if user.role == "admin":
        return True
    row = db.execute(
        select(KbMember.id).where(KbMember.kb_id == kb_id, KbMember.user_id == user.id).limit(1)
    ).first()
    return row is not None


def _get_kb_or_404(db: Session, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return kb


@router.get("", response_model=KbListResponse)
def list_kbs(
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> KbListResponse:
    """admin 全部；user 仅成员可见。"""
    if user.role == "admin":
        rows = db.execute(select(KnowledgeBase).order_by(KnowledgeBase.id)).scalars()
    else:
        rows = db.execute(
            select(KnowledgeBase)
            .join(KbMember, KbMember.kb_id == KnowledgeBase.id)
            .where(KbMember.user_id == user.id)
            .order_by(KnowledgeBase.id)
        ).scalars()
    return KbListResponse(items=[_kb_to_response(kb) for kb in rows])


@router.post("", response_model=KbResponse, status_code=status.HTTP_201_CREATED)
def create_kb(
    body: KbCreateRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> KbResponse:
    kb = KnowledgeBase(name=body.name, description=body.description, created_by=_.id, status=1)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    # 创建者自动成为成员（便于非 admin 后续扩展；admin 本身全权限）
    db.add(KbMember(kb_id=kb.id, user_id=_.id))
    db.commit()
    return _kb_to_response(kb)


@router.get("/{kb_id}", response_model=KbResponse)
def get_kb(
    kb_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> KbResponse:
    kb = _get_kb_or_404(db, kb_id)
    if not _is_member(db, kb_id, user):
        # 非成员：资源不存在或禁止——统一 404，避免枚举
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return _kb_to_response(kb)


@router.put("/{kb_id}", response_model=KbResponse)
def update_kb(
    kb_id: int,
    body: KbUpdateRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> KbResponse:
    kb = _get_kb_or_404(db, kb_id)
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.status is not None:
        kb.status = body.status
    db.commit()
    db.refresh(kb)
    return _kb_to_response(kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb(
    kb_id: int,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> None:
    """级联物理删除：documents 记录 → uploads 文件 → sessions/messages → Chroma（M2 接通）。"""
    kb = _get_kb_or_404(db, kb_id)

    # 1. 物理文件（在删记录前收集 stored_name）
    stored_names = (
        db.execute(select(Document.stored_name).where(Document.kb_id == kb_id)).scalars().all()
    )
    upload_dir = Path(settings.upload_dir)

    try:
        # 2. 消息与会话（FK 由 DB 级联，这里显式删保险）
        session_ids = select(ChatSession.id).where(ChatSession.kb_id == kb_id)
        db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids)))
        db.execute(delete(ChatSession).where(ChatSession.kb_id == kb_id))

        # 3. 文档记录
        db.execute(delete(Document).where(Document.kb_id == kb_id))

        # 4. 成员
        db.execute(delete(KbMember).where(KbMember.kb_id == kb_id))

        # 5. KB 本体
        db.delete(kb)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="删除知识库失败") from None

    # 6. 物理文件（DB 提交成功后）
    for name in stored_names:
        path = upload_dir / name
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass  # 文件清理失败不回滚 DB

    # 7. Chroma collection：M1 留接口，M2 接通；容忍不存在
    try:
        from app.services.vector import delete_collection  # 延迟导入，M2 实现

        delete_collection(kb_id)
    except Exception:
        pass


# ---------- 成员子路由 ----------


@router.get("/{kb_id}/members", response_model=list[KbMemberResponse])
def list_members(
    kb_id: int,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> list[KbMemberResponse]:
    if not _is_member(db, kb_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    _get_kb_or_404(db, kb_id)
    rows = db.execute(
        select(KbMember, User)
        .join(User, User.id == KbMember.user_id)
        .where(KbMember.kb_id == kb_id)
        .order_by(KbMember.id)
    ).all()
    return [
        KbMemberResponse(
            id=m.id,
            kb_id=m.kb_id,
            user_id=m.user_id,
            username=u.username,
            nickname=u.nickname,
            role=u.role,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m, u in rows
    ]


@router.post(
    "/{kb_id}/members", response_model=KbMemberResponse, status_code=status.HTTP_201_CREATED
)
def add_member(
    kb_id: int,
    body: KbMemberAddRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> KbMemberResponse:
    _get_kb_or_404(db, kb_id)
    target = db.get(User, body.user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    exists_row = db.execute(
        select(KbMember).where(KbMember.kb_id == kb_id, KbMember.user_id == body.user_id)
    ).scalar_one_or_none()
    if exists_row is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已是成员")
    member = KbMember(kb_id=kb_id, user_id=body.user_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    return KbMemberResponse(
        id=member.id,
        kb_id=member.kb_id,
        user_id=member.user_id,
        username=target.username,
        nickname=target.nickname,
        role=target.role,
        created_at=member.created_at.isoformat() if member.created_at else None,
    )


@router.delete("/{kb_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    kb_id: int,
    user_id: int,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> None:
    _get_kb_or_404(db, kb_id)
    member = db.execute(
        select(KbMember).where(KbMember.kb_id == kb_id, KbMember.user_id == user_id)
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    db.delete(member)
    db.commit()
