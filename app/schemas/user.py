"""用户管理请求/响应。"""

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    username: str
    nickname: str
    role: str
    status: int
    created_at: str | None = None

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=64)
    role: str = Field(default="user", pattern=r"^(admin|user)$")


class UserUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)
    role: str | None = Field(default=None, pattern=r"^(admin|user)$")
    status: int | None = Field(default=None, ge=0, le=1)


class UserPasswordRequest(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]
