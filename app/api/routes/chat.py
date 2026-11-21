"""SSE 流式问答：sources → thinking×N → delta×N → done。"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.knowledge_bases import _get_kb_or_404, _is_member
from app.core.security import login_required
from app.db import get_db
from app.models import ChatMessage, ChatSession, User
from app.schemas import AskRequest
from app.services.llm import RAG_SYSTEM_PROMPT, create_provider
from app.services.vector import search

router = APIRouter(prefix="/api/chat", tags=["chat"])

FALLBACK_ANSWER = "未找到相关内容，请换个问法"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ensure_session(
    db: Session, user: User, kb_id: int, session_id: int | None, question: str
) -> ChatSession:
    if session_id is not None:
        sess = db.get(ChatSession, session_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if sess.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="无权访问该会话")
        return sess
    title = question[:20]
    sess = ChatSession(user_id=user.id, kb_id=kb_id, title=title)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.post("/ask")
def ask(
    body: AskRequest,
    user: User = Depends(login_required),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """无权限时在进 SSE 前直接 JSON 401/403。"""
    _get_kb_or_404(db, body.kb_id)
    if not _is_member(db, body.kb_id, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该知识库")

    # 检索
    provider = create_provider()
    try:
        q_emb = provider.embed([body.question])[0]
        sources = search(kb_id=body.kb_id, query_embedding=q_emb)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"检索服务异常: {exc}",
        ) from exc

    session = _ensure_session(db, user, body.kb_id, body.session_id, body.question)

    def event_stream() -> Iterator[str]:
        yield _sse("sources", {"sources": sources})

        if not sources:
            # 零命中：兜底文案，不算错误
            yield _sse("delta", {"content": FALLBACK_ANSWER})
            answer = FALLBACK_ANSWER
        else:
            context = "\n\n".join(
                f"[{s['file_name']} #{s['chunk_index']}]\n{s['snippet']}" for s in sources
            )
            parts: list[str] = []
            try:
                for kind, text in provider.chat_stream(RAG_SYSTEM_PROMPT, body.question, context):
                    if kind == "thinking":
                        yield _sse("thinking", {"content": text})
                    else:
                        parts.append(text)
                        yield _sse("delta", {"content": text})
            except Exception as exc:
                yield _sse("error", {"message": f"问答服务异常: {exc}"})
                return
            answer = "".join(parts)

        # 落库（thinking 不落库）
        try:
            from datetime import UTC, datetime

            msg = ChatMessage(
                session_id=session.id,
                user_id=user.id,
                kb_id=body.kb_id,
                question=body.question,
                answer=answer,
                sources=sources,
            )
            db.add(msg)
            session.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            db.refresh(msg)
            yield _sse("done", {"session_id": session.id, "message_id": msg.id})
        except Exception as exc:
            db.rollback()
            yield _sse("error", {"message": f"保存回答失败: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
