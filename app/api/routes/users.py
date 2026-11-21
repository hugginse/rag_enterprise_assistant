"""用户管理（admin）。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import admin_required, hash_password
from app.db import get_db
from app.models import User
from app.schemas import (
    UserCreateRequest,
    UserListResponse,
    UserPasswordRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/users", tags=["users"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.get("", response_model=UserListResponse)
def list_users(
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> UserListResponse:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.execute(
        select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).scalars()
    return UserListResponse(total=total, items=[_to_response(u) for u in users])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> UserResponse:
    exists = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
        role=body.role,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.put("/{user_id}/password", response_model=UserResponse)
def reset_password(
    user_id: int,
    body: UserPasswordRequest,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.delete("/{user_id}", response_model=UserResponse)
def disable_user(
    user_id: int,
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> UserResponse:
    """删除 = 禁用（status=0），不物理删。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.status = 0
    db.commit()
    db.refresh(user)
    return _to_response(user)
