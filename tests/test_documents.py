"""文档上传/类型/超限/删除测试。"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import login

SEED = Path("seed_docs")


def _sample_file() -> tuple[str, bytes]:
    # 找一份真实 seed txt
    files = list(SEED.rglob("*.txt"))
    assert files, "seed_docs 需含 txt"
    p = files[0]
    return p.name, p.read_bytes()


def test_upload_ok(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    name, data = _sample_file()
    r = client.post(
        "/api/documents",
        headers=headers,
        data={"kb_id": str(seed_kb.id)},
        files={"file": (name, data, "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["filename"] == name

    # 列表可见
    r = client.get(f"/api/documents?kb_id={seed_kb.id}", headers=headers)
    assert r.status_code == 200
    assert any(d["id"] == body["id"] for d in r.json()["items"])

    # 删除
    r = client.delete(f"/api/documents/{body['id']}", headers=headers)
    assert r.status_code == 204


def test_upload_reject_bad_type(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.post(
        "/api/documents",
        headers=headers,
        data={"kb_id": str(seed_kb.id)},
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_upload_reject_oversize(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    max_mb = get_settings().upload_max_mb
    payload = b"a" * (max_mb * 1024 * 1024 + 1)
    r = client.post(
        "/api/documents",
        headers=headers,
        data={"kb_id": str(seed_kb.id)},
        files={"file": ("big.txt", payload, "text/plain")},
    )
    assert r.status_code == 400
    assert str(max_mb) in r.json()["detail"]


def test_upload_requires_admin(client: TestClient, seed_kb, seed_users):
    headers = login(client, "member", "member123")
    name, data = _sample_file()
    r = client.post(
        "/api/documents",
        headers=headers,
        data={"kb_id": str(seed_kb.id)},
        files={"file": (name, data, "text/plain")},
    )
    assert r.status_code == 403


def test_outsider_cannot_list_documents(client: TestClient, seed_kb, seed_users):
    headers = login(client, "outsider", "outside123")
    r = client.get(f"/api/documents?kb_id={seed_kb.id}", headers=headers)
    assert r.status_code == 404


def test_get_document_404_for_outsider(client: TestClient, seed_kb, seed_users, db_session):

    admin = login(client, "admin", "admin123")
    name, data = _sample_file()
    r = client.post(
        "/api/documents",
        headers=admin,
        data={"kb_id": str(seed_kb.id)},
        files={"file": (name, data, "text/plain")},
    )
    doc_id = r.json()["id"]

    outsider = login(client, "outsider", "outside123")
    r = client.get(f"/api/documents/{doc_id}", headers=outsider)
    assert r.status_code == 404
