"""认证测试：登录、错误密码、过期/无效 token、禁用用户 401。"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import login


def test_login_success(client: TestClient, seed_users):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert data["token"]
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_login_wrong_password(client: TestClient, seed_users):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    assert r.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    r = client.post("/api/auth/login", json={"username": "nope", "password": "x"})
    assert r.status_code == 401


def test_login_disabled_user(client: TestClient, seed_users):
    r = client.post("/api/auth/login", json={"username": "disabled", "password": "disabled123"})
    assert r.status_code == 401


def test_me_requires_token(client: TestClient):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_ok(client: TestClient, seed_users):
    headers = login(client, "admin", "admin123")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_expired_token_401(client: TestClient, seed_users):
    settings = get_settings()
    expire = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(seed_users["admin"].id), "role": "admin", "exp": expire},
        settings.secret_key,
        algorithm="HS256",
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_invalid_token_401(client: TestClient):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_disabled_user_existing_token_401(client: TestClient, seed_users):
    """禁用用户（status=0）：登录拒绝 + 存量 JWT 立即 401。"""
    from app.core.security import create_token

    r_login = client.post(
        "/api/auth/login", json={"username": "disabled", "password": "disabled123"}
    )
    assert r_login.status_code == 401

    token = create_token(seed_users["disabled"].id, "user")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
