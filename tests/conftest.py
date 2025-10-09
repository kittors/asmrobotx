"""测试夹具：为 pytest 提供数据库与客户端的共享配置。"""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.packages.system.core.dependencies import get_db
from app.packages.system.db import session as db_session
from app.packages.system.db.init_db import init_db
from app.packages.system.models.base import Base
from app.main import app

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """创建隔离的 SQLite 测试数据库，并在会话结束后清理。"""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db_session.engine = engine
    db_session.SessionLocal = TestingSessionLocal

    Base.metadata.create_all(bind=engine)
    init_db()
    yield

    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture()
def db_session_fixture() -> Generator[Session, None, None]:
    """提供给测试用例使用的数据库会话。"""
    session = db_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session_fixture):
    """构建 FastAPI TestClient，并注入测试专用的数据库依赖。"""
    def override_get_db() -> Generator[Session, None, None]:
        session = db_session.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
