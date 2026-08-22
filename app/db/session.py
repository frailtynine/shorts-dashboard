from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine():
    return create_engine(
        get_settings().sqlite_url,
        connect_args={"check_same_thread": False},
    )


@lru_cache
def get_session_maker():
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        class_=Session,
    )


def create_db_session() -> Session:
    return get_session_maker()()


@contextmanager
def session_scope():
    session = create_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Session:
    session = create_db_session()
    try:
        yield session
    finally:
        session.close()
