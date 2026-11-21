"""会话与消息响应。"""

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    id: int
    user_id: int
    kb_id: int
    title: str
    created_at: str | None = None
    updated_at: str | None = None


class SessionCreateRequest(BaseModel):
    kb_id: int
    title: str = Field(default="", max_length=64)


class SessionPatchRequest(BaseModel):
    title: str = Field(min_length=1, max_length=64)


class SessionListResponse(BaseModel):
    items: list[SessionResponse]


class SourceItem(BaseModel):
    file_name: str = ""
    chunk_index: int = -1
    score: float = 0.0
    snippet: str = ""


class MessageResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    kb_id: int
    question: str
    answer: str
    sources: list[SourceItem] = []
    created_at: str | None = None


class MessageListResponse(BaseModel):
    items: list[MessageResponse]


class HistoryResponse(BaseModel):
    total: int
    items: list[MessageResponse]
