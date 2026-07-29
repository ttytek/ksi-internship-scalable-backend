"""Wspólna baza deklaratywna SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base dla wszystkich modeli ORM."""
