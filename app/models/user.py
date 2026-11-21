"""用户模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")  # admin | user
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1 启用 | 0 禁用
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
