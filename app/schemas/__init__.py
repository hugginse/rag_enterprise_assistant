"""Pydantic 请求/响应模型。"""

from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, TokenUser
from app.schemas.chat import AskRequest
from app.schemas.chat_session import (
    HistoryResponse,
    MessageListResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionPatchRequest,
    SessionResponse,
    SourceItem,
)
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.knowledge_base import (
    KbCreateRequest,
    KbListResponse,
    KbMemberAddRequest,
    KbMemberResponse,
    KbResponse,
    KbUpdateRequest,
)
from app.schemas.stats import DashboardResponse, TrendPoint
from app.schemas.user import (
    UserCreateRequest,
    UserListResponse,
    UserPasswordRequest,
    UserResponse,
    UserUpdateRequest,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "MeResponse",
    "TokenUser",
    "AskRequest",
    "HistoryResponse",
    "MessageListResponse",
    "MessageResponse",
    "SessionCreateRequest",
    "SessionListResponse",
    "SessionPatchRequest",
    "SessionResponse",
    "SourceItem",
    "DocumentListResponse",
    "DocumentResponse",
    "KbCreateRequest",
    "KbListResponse",
    "KbMemberAddRequest",
    "KbMemberResponse",
    "KbResponse",
    "KbUpdateRequest",
    "DashboardResponse",
    "TrendPoint",
    "UserCreateRequest",
    "UserListResponse",
    "UserPasswordRequest",
    "UserResponse",
    "UserUpdateRequest",
]
