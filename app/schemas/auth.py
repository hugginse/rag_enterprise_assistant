"""认证相关请求/响应。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenUser(BaseModel):
    id: int
    username: str
    nickname: str
    role: str
    status: int


class LoginResponse(BaseModel):
    token: str
    user: TokenUser


class MeResponse(TokenUser):
    created_at: str | None = None
