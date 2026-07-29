"""Zależności FastAPI."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from ksi.db.session import get_db as _get_db


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()
