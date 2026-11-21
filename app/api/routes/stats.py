"""管理端统计。"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import admin_required
from app.db import get_db
from app.models import ChatMessage, Document, KnowledgeBase, User
from app.schemas import DashboardResponse, TrendPoint

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    _: User = Depends(admin_required),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    kbs = db.scalar(select(func.count()).select_from(KnowledgeBase)) or 0
    documents = db.scalar(select(func.count()).select_from(Document)) or 0
    messages = db.scalar(select(func.count()).select_from(ChatMessage)) or 0

    # 近 7 天（含今天）问答趋势，按日聚合
    today = datetime.now(UTC).date()
    start = datetime.combine(today - timedelta(days=6), datetime.min.time(), tzinfo=UTC)
    rows = db.execute(
        select(
            func.date(ChatMessage.created_at).label("d"),
            func.count().label("c"),
        )
        .where(ChatMessage.created_at >= start)
        .group_by(func.date(ChatMessage.created_at))
        .order_by(func.date(ChatMessage.created_at))
    ).all()
    count_by_date = {str(r.d): r.c for r in rows}

    trend: list[TrendPoint] = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        key = day.isoformat()
        trend.append(TrendPoint(date=key, count=count_by_date.get(key, 0)))

    return DashboardResponse(
        users=users,
        kbs=kbs,
        documents=documents,
        messages=messages,
        trend=trend,
    )
