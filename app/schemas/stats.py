"""统计响应。"""

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str
    count: int


class DashboardResponse(BaseModel):
    users: int
    kbs: int
    documents: int
    messages: int
    trend: list[TrendPoint]
