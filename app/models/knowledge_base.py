"""知识库与成员模型。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    members: Mapped[list["KbMember"]] = relationship(
        back_populates="kb", cascade="all, delete-orphan", passive_deletes=True
    )


class KbMember(Base):
    __tablename__ = "kb_members"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_members_kb_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    kb: Mapped[KnowledgeBase] = relationship(back_populates="members")
