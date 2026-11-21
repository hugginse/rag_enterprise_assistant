"""问答请求。"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    kb_id: int
    session_id: int | None = None
