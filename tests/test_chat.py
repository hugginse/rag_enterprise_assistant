"""SSE 事件顺序、RAG mock、零命中、权限与级联删除测试。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.models import ChatMessage, ChatSession
from tests.conftest import login

# ---------- Mock Provider / 检索 ----------


class MockProvider:
    """固定产出：thinking×2 + delta×3。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def chat_stream(self, system: str, question: str, context: str) -> Iterator[tuple[str, str]]:
        yield ("thinking", "思考一")
        yield ("thinking", "思考二")
        yield ("delta", "答案A")
        yield ("delta", "答案B")
        yield ("delta", "答案C")


class MockEmptyProvider(MockProvider):
    def chat_stream(self, system, question, context):  # noqa: ANN001
        yield ("delta", "不应出现")


FIXED_SOURCES = [
    {
        "file_name": "员工请假管理办法.md",
        "chunk_index": 0,
        "score": 0.66,
        "snippet": "请假流程片段",
    },
    {
        "file_name": "公司考勤管理制度.txt",
        "chunk_index": 2,
        "score": 0.51,
        "snippet": "考勤片段",
    },
]


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    import json

    events: list[tuple[str, dict]] = []
    event_name = None
    for line in body.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event_name:
            data = json.loads(line.split(":", 1)[1].strip())
            events.append((event_name, data))
            event_name = None
    return events


@pytest.fixture()
def mock_chat(monkeypatch):
    import app.api.routes.chat as chat_mod

    monkeypatch.setattr(chat_mod, "create_provider", lambda: MockProvider())
    monkeypatch.setattr(chat_mod, "search", lambda **kwargs: list(FIXED_SOURCES))
    return chat_mod


@pytest.fixture()
def mock_chat_zero(monkeypatch):
    import app.api.routes.chat as chat_mod

    monkeypatch.setattr(chat_mod, "create_provider", lambda: MockEmptyProvider())
    monkeypatch.setattr(chat_mod, "search", lambda **kwargs: [])
    return chat_mod


def _ask(client: TestClient, headers: dict, kb_id: int, question: str = "请假提前几天"):
    r = client.post(
        "/api/chat/ask",
        json={"question": question, "kb_id": kb_id},
        headers=headers,
    )
    return r


def test_sse_event_order_and_persistence(client, seed_kb, seed_users, mock_chat):
    headers = login(client, "member", "member123")
    r = _ask(client, headers, seed_kb.id)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    events = _parse_sse(r.text)
    names = [e[0] for e in events]
    # 顺序：sources → thinking×N → delta×N → done
    assert names[0] == "sources"
    assert names[-1] == "done"
    assert "thinking" in names
    assert names.index("thinking") < names.index("delta")
    # thinking 全部在 delta 之前
    first_delta = names.index("delta")
    assert all(i < first_delta for i, n in enumerate(names) if n == "thinking")
    # done 前无 error
    assert "error" not in names

    # 逐段：delta 至少 3 段独立事件
    deltas = [d["content"] for n, d in events if n == "delta"]
    assert deltas == ["答案A", "答案B", "答案C"]
    thinkings = [d["content"] for n, d in events if n == "thinking"]
    assert thinkings == ["思考一", "思考二"]

    # sources 内容
    src = events[0][1]["sources"]
    assert src[0]["file_name"] == "员工请假管理办法.md"
    assert src[0]["score"] == pytest.approx(0.66)

    # 落库：answer 为 delta 拼接；thinking 不落库
    done = events[-1][1]
    assert done["session_id"] > 0
    msg = client.get(f"/api/chat/sessions/{done['session_id']}/messages", headers=headers).json()
    assert len(msg["items"]) == 1
    assert msg["items"][0]["answer"] == "答案A答案B答案C"
    assert "思考一" not in msg["items"][0]["answer"]
    assert msg["items"][0]["sources"][0]["file_name"] == "员工请假管理办法.md"


def test_sse_zero_hit_fallback(client, seed_kb, seed_users, mock_chat_zero):
    headers = login(client, "member", "member123")
    r = _ask(client, headers, seed_kb.id, question="完全无关的问题xyz")
    assert r.status_code == 200
    events = _parse_sse(r.text)
    names = [e[0] for e in events]
    assert names[0] == "sources"
    assert events[0][1]["sources"] == []
    assert "delta" in names
    assert "done" in names
    delta_text = "".join(d["content"] for n, d in events if n == "delta")
    assert "未找到相关内容" in delta_text
    # 不应调用模型产生多段假答案
    deltas = [d for n, d in events if n == "delta"]
    assert len(deltas) == 1


def test_sse_non_member_403(client, seed_kb, seed_users, mock_chat):
    headers = login(client, "outsider", "outside123")
    r = _ask(client, headers, seed_kb.id)
    assert r.status_code == 403
    assert "text/event-stream" not in r.headers.get("content-type", "")
    assert r.json()["detail"]


def test_sse_unauthorized_401(client, seed_kb):
    r = client.post("/api/chat/ask", json={"question": "x", "kb_id": seed_kb.id})
    assert r.status_code == 401


def test_session_cascade_delete(client, seed_kb, seed_users, mock_chat, db_session):
    headers = login(client, "member", "member123")
    r = _ask(client, headers, seed_kb.id, question="级联删除测试问题")
    events = _parse_sse(r.text)
    session_id = events[-1][1]["session_id"]
    message_id = events[-1][1]["message_id"]

    # 确认有消息
    msgs = client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert msgs.status_code == 200
    assert len(msgs.json()["items"]) == 1

    # 删除会话
    r = client.delete(f"/api/chat/sessions/{session_id}", headers=headers)
    assert r.status_code == 204

    # 消息与会话均不存在
    assert db_session.get(ChatSession, session_id) is None
    assert db_session.get(ChatMessage, message_id) is None
    r = client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert r.status_code == 404


def test_ask_with_explicit_session(client, seed_kb, seed_users, mock_chat):
    headers = login(client, "member", "member123")
    # 先建会话
    s = client.post(
        "/api/chat/sessions",
        json={"kb_id": seed_kb.id, "title": "t"},
        headers=headers,
    )
    sid = s.json()["id"]

    r = client.post(
        "/api/chat/ask",
        json={"question": "指定会话提问", "kb_id": seed_kb.id, "session_id": sid},
        headers=headers,
    )
    events = _parse_sse(r.text)
    assert events[-1][0] == "done"
    assert events[-1][1]["session_id"] == sid

    msgs = client.get(f"/api/chat/sessions/{sid}/messages", headers=headers).json()
    assert len(msgs["items"]) == 1
