"""Dépendances FastAPI partagées (fabrique de sessions DB)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from ..db.session import make_engine, make_sessionmaker


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Fabrique de sessions (engine mis en cache). Surchargée en test (SQLite)."""
    return make_sessionmaker(make_engine())
