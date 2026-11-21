"""pytest fixtures：测试库、应用工厂、通用账号/Kb。"""

import os
from collections.abc import Generator

# 必须在导入 app 之前指向测试库
os.environ["DATABASE_URL"] = "postgresql+psycopg2://rag:rag123@localhost:5432/rag_enterprise_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    ChatMessage,
    ChatSession,
    Document,
    KbMember,
    KnowledgeBase,
    User,
)

get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_engine():
    """测试库 engine；session 级建表。"""
    settings = get_settings()
    assert "rag_enterprise_test" in settings.database_url, settings.database_url
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # 用例间清空，避免唯一键冲突
        with TestSession() as clean:
            for table in (
                ChatMessage.__table__,
                ChatSession.__table__,
                Document.__table__,
                KbMember.__table__,
                KnowledgeBase.__table__,
                User.__table__,
            ):
                clean.execute(table.delete())
            clean.commit()


@pytest.fixture()
def app(test_engine, db_session):
    application = create_app()

    def _override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seed_users(db_session) -> dict[str, User]:
    """admin + member_user + outsider 三个账号。"""
    users = {
        "admin": User(
            username="admin",
            password_hash=hash_password("admin123"),
            nickname="管理员",
            role="admin",
            status=1,
        ),
        "member": User(
            username="member",
            password_hash=hash_password("member123"),
            nickname="成员",
            role="user",
            status=1,
        ),
        "outsider": User(
            username="outsider",
            password_hash=hash_password("outside123"),
            nickname="局外人",
            role="user",
            status=1,
        ),
        "disabled": User(
            username="disabled",
            password_hash=hash_password("disabled123"),
            nickname="禁用",
            role="user",
            status=0,
        ),
    }
    for u in users.values():
        db_session.add(u)
    db_session.commit()
    for u in users.values():
        db_session.refresh(u)
    return users


@pytest.fixture()
def seed_kb(db_session, seed_users) -> KnowledgeBase:
    kb = KnowledgeBase(name="测试库", description="fixture", created_by=seed_users["admin"].id)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    db_session.add(KbMember(kb_id=kb.id, user_id=seed_users["admin"].id))
    db_session.add(KbMember(kb_id=kb.id, user_id=seed_users["member"].id))
    db_session.commit()
    return kb


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
