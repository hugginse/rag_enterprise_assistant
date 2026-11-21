"""知识库与成员请求/响应。"""

from pydantic import BaseModel, Field


class KbResponse(BaseModel):
    id: int
    name: str
    description: str
    created_by: int
    status: int
    created_at: str | None = None


class KbCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)


class KbUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    status: int | None = Field(default=None, ge=0, le=1)


class KbMemberResponse(BaseModel):
    id: int
    kb_id: int
    user_id: int
    username: str = ""
    nickname: str = ""
    role: str = ""
    created_at: str | None = None


class KbMemberAddRequest(BaseModel):
    user_id: int


class KbListResponse(BaseModel):
    items: list[KbResponse]
