"""Tests du capability token du feed ICS (§2.6) sur SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from contract_intelligence.alerting import creer_token, resoudre_token, revoquer, roter
from contract_intelligence.db import Base, make_sessionmaker


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def test_creer_et_resoudre(factory) -> None:
    with factory() as s:
        token, ft = creer_token(s, "acme", "alice")
        s.commit()
        tid = ft.id
    with factory() as s:
        resolu = resoudre_token(s, token)
        assert resolu is not None
        assert resolu.id == tid
        assert resolu.tenant == "acme"
        # Le token n'est jamais stocké en clair.
        assert resolu.token_hash != token


def test_revocation(factory) -> None:
    with factory() as s:
        token, ft = creer_token(s, "acme", "alice")
        revoquer(s, ft.id)
        s.commit()
    with factory() as s:
        assert resoudre_token(s, token) is None


def test_rotation(factory) -> None:
    with factory() as s:
        ancien, ft = creer_token(s, "acme", "alice")
        nouveau = roter(s, ft.id)
        s.commit()
    assert nouveau is not None and nouveau != ancien
    with factory() as s:
        assert resoudre_token(s, ancien) is None
        assert resoudre_token(s, nouveau) is not None
