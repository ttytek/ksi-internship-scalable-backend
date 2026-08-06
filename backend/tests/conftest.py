"""Shared pytest fixtures."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import ksi.domain.entities  # noqa: F401 — rejestracja tabel
from ksi.api.deps import get_db
from ksi.db import session as db_mod
from ksi.db.base import Base
from ksi.domain.entities import Task, TaskTest, User
from ksi.domain.enums import TaskJudgeMode, TestVisibility
from ksi.main import create_app


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine, session_factory) -> Generator[TestClient, None, None]:
    # Lifespan create_all + sędzia używają globalnego engine/factory — podmień na SQLite.
    original_engine = db_mod._engine
    original_factory = db_mod._session_factory
    db_mod._engine = db_engine
    db_mod._session_factory = session_factory

    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    db_mod._engine = original_engine
    db_mod._session_factory = original_factory


@pytest.fixture()
def sample_user(db_session: Session) -> User:
    user = User(id=uuid4(), username="alice")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def sample_task(db_session: Session) -> Task:
    task = Task(
        id=uuid4(),
        slug="echo",
        title="Echo",
        statement="Wypisz to samo co na wejściu.",
        judge_mode=TaskJudgeMode.SIMPLE,
        time_limit_ms=2000,
        memory_limit_mb=256,
        is_published=True,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(
        TaskTest(
            task_id=task.id,
            ordinal=1,
            visibility=TestVisibility.PUBLIC,
            input="hello\n",
            expected_output="hello\n",
            points=1,
        )
    )
    db_session.add(
        TaskTest(
            task_id=task.id,
            ordinal=2,
            visibility=TestVisibility.HIDDEN,
            input="world\n",
            expected_output="world\n",
            points=1,
        )
    )
    db_session.commit()
    db_session.refresh(task)
    return task
