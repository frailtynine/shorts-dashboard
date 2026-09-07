from collections.abc import Generator
from functools import lru_cache

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()

    @lru_cache
    def fake_settings() -> Settings:
        return Settings()

    original_settings = get_settings
    import app.main as main_module

    main_module.get_settings = fake_settings
    main_module.worker.start = lambda: None
    main_module.worker.stop = lambda: None

    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    main_module.get_settings = original_settings
    get_settings.cache_clear()
