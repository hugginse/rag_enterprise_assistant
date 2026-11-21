"""管理端统计测试。"""

from fastapi.testclient import TestClient

from tests.conftest import login


def test_dashboard_admin_ok(client: TestClient, seed_kb, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.get("/api/stats/dashboard", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["users"] >= 3
    assert data["kbs"] >= 1
    assert data["documents"] >= 0
    assert data["messages"] >= 0
    assert len(data["trend"]) == 7
    for point in data["trend"]:
        assert "date" in point and "count" in point
        assert point["count"] >= 0


def test_dashboard_forbidden_for_user(client: TestClient, seed_users):
    headers = login(client, "member", "member123")
    r = client.get("/api/stats/dashboard", headers=headers)
    assert r.status_code == 403


def test_dashboard_unauthorized(client: TestClient):
    r = client.get("/api/stats/dashboard")
    assert r.status_code == 401
