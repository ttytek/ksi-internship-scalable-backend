"""Checker pytest fixtures (SQLite + in-memory S3)."""

from collections.abc import Generator
from uuid import uuid4

import ksi.domain.entities  # noqa: F401
import pytest
from ksi.db import session as db_mod
from ksi.db.base import Base
from ksi.db.schema import ensure_schema
from ksi.domain.entities import Task, TaskTest, User
from ksi.domain.enums import TaskJudgeMode, TestVisibility
from ksi.services.pack_attach import attach_main_pack
from ksi.services.storage import InMemoryStorage, reset_overrides, set_cache_dir, set_storage
from ksi.services.test_pack import build_pack
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path) -> Generator[None, None, None]:
    reset_overrides()
    set_cache_dir(tmp_path / "ksi-pack-cache")
    yield
    reset_overrides()


@pytest.fixture()
def fake_storage() -> InMemoryStorage:
    store = InMemoryStorage()
    set_storage(store)
    return store


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

    ensure_schema(engine)
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


@pytest.fixture(autouse=True)
def _patch_engine(db_engine, session_factory) -> Generator[None, None, None]:
    original_engine = db_mod._engine
    original_factory = db_mod._session_factory
    db_mod._engine = db_engine
    db_mod._session_factory = session_factory
    yield
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
def sample_task(db_session: Session, fake_storage: InMemoryStorage) -> Task:
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
            points=0,
        )
    )
    attach_main_pack(
        db_session,
        task,
        build_pack([("world\n", "world\n", 1)]),
        storage=fake_storage,
    )
    db_session.commit()
    db_session.refresh(task)
    return task
