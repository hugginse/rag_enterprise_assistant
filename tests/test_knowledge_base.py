"""知识库权限矩阵：非成员 404、admin 全过、授权后可见。"""

from fastapi.testclient import TestClient

from tests.conftest import login


def test_admin_lists_all_kbs(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.get("/api/knowledge-bases", headers=headers)
    assert r.status_code == 200
    names = [k["name"] for k in r.json()["items"]]
    assert "测试库" in names


def test_member_lists_kb(client: TestClient, seed_kb, seed_users):
    headers = login(client, "member", "member123")
    r = client.get("/api/knowledge-bases", headers=headers)
    assert r.status_code == 200
    assert any(k["id"] == seed_kb.id for k in r.json()["items"])


def test_outsider_lists_empty(client: TestClient, seed_kb, seed_users):
    headers = login(client, "outsider", "outside123")
    r = client.get("/api/knowledge-bases", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_outsider_get_kb_404(client: TestClient, seed_kb, seed_users):
    headers = login(client, "outsider", "outside123")
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=headers)
    assert r.status_code == 404


def test_member_get_kb_200(client: TestClient, seed_kb, seed_users):
    headers = login(client, "member", "member123")
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == seed_kb.id


def test_admin_get_kb_200(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=headers)
    assert r.status_code == 200


def test_outsider_documents_404(client: TestClient, seed_kb, seed_users):
    headers = login(client, "outsider", "outside123")
    r = client.get(f"/api/documents?kb_id={seed_kb.id}", headers=headers)
    assert r.status_code == 404


def test_member_documents_200(client: TestClient, seed_kb, seed_users):
    headers = login(client, "member", "member123")
    r = client.get(f"/api/documents?kb_id={seed_kb.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_user_cannot_create_kb(client: TestClient, seed_users):
    headers = login(client, "member", "member123")
    r = client.post("/api/knowledge-bases", json={"name": "x"}, headers=headers)
    assert r.status_code == 403


def test_user_cannot_delete_kb(client: TestClient, seed_kb, seed_users):
    headers = login(client, "member", "member123")
    r = client.delete(f"/api/knowledge-bases/{seed_kb.id}", headers=headers)
    assert r.status_code == 403


def test_admin_crud_kb(client: TestClient, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.post(
        "/api/knowledge-bases",
        json={"name": "CRUD库", "description": "d"},
        headers=headers,
    )
    assert r.status_code == 201
    kb_id = r.json()["id"]

    r = client.put(
        f"/api/knowledge-bases/{kb_id}",
        json={"name": "CRUD库改"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "CRUD库改"

    r = client.delete(f"/api/knowledge-bases/{kb_id}", headers=headers)
    assert r.status_code == 204


def test_authorization_flow_outsider_becomes_member(
    client: TestClient, seed_kb, seed_users, db_session
):
    """授权后 member/outsider 可见；移除后 404。"""
    admin = login(client, "admin", "admin123")
    outsider = login(client, "outsider", "outside123")

    # 授权前 404
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=outsider)
    assert r.status_code == 404

    # 授权
    r = client.post(
        f"/api/knowledge-bases/{seed_kb.id}/members",
        json={"user_id": seed_users["outsider"].id},
        headers=admin,
    )
    assert r.status_code == 201

    # 授权后 200
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=outsider)
    assert r.status_code == 200

    # 移除
    r = client.delete(
        f"/api/knowledge-bases/{seed_kb.id}/members/{seed_users['outsider'].id}",
        headers=admin,
    )
    assert r.status_code == 204

    # 移除后 404
    r = client.get(f"/api/knowledge-bases/{seed_kb.id}", headers=outsider)
    assert r.status_code == 404
