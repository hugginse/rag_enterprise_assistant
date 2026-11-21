"""文档请求/响应。"""

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    error_msg: str | None = None
    chunk_count: int
    created_by: int
    created_at: str | None = None
    updated_at: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
