"""Moteur, sessions, et session liée au tenant (support RLS)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, future=True)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def tenant_session(factory: sessionmaker[Session], tenant: str) -> Iterator[Session]:
    """Session PostgreSQL bornée à un tenant pour la RLS.

    `set_config('app.current_tenant', tenant, is_local => true)` limite le réglage
    à la transaction courante ; les politiques RLS comparent `tenant` à ce GUC.
    Le tenant provient du token, jamais du client (§7).
    """
    with factory() as session, session.begin():
        # `set_config` est spécifique PostgreSQL ; no-op ailleurs (ex. SQLite en test).
        if session.get_bind().dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": tenant},
            )
        yield session
