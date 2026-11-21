"""登录与当前用户。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token, login_required, verify_password
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse, MeResponse, TokenUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_user(user: User) -> TokenUser:
    return TokenUser(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        role=user.role,
        status=user.status,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if user.status == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已禁用")
    token = create_token(user.id, user.role)
    return LoginResponse(token=token, user=_token_user(user))


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(login_required)) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )
