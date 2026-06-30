"""Test de bout en bout de l'abonnement + feed ICS via l'API."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contract_intelligence.api.app import app
from contract_intelligence.api.auth import Principal, get_principal
from contract_intelligence.api.deps import get_session_factory
from contract_intelligence.db import Base, Contrat, make_sessionmaker


@pytest.fixture
def factory():
    # StaticPool : une seule connexion partagée → la base in-memory survit aux
    # threads (l'endpoint sync FastAPI s'exécute dans un worker distinct du test).
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                reference="C-1",
                date_echeance=date(2025, 12, 31),
                date_limite_denonciation=date(2025, 9, 30),
            )
        )
        s.commit()
    return f


def test_abonnement_puis_feed(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_principal] = lambda: Principal(
        sujet="alice", tenant="acme", claims={}
    )
    try:
        with TestClient(app) as client:
            resp = client.post("/ics/abonnement")
            assert resp.status_code == 201
            url = resp.json()["url"]

            feed = client.get(url)
            assert feed.status_code == 200
            assert feed.headers["content-type"].startswith("text/calendar")
            assert "BEGIN:VCALENDAR" in feed.text
            assert "Échéance — C-1" in feed.text
            assert "VALARM" not in feed.text

            # Tenant globex ne voit pas le contrat acme dans son feed.
    finally:
        app.dependency_overrides.clear()


def test_feed_token_inconnu(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    try:
        with TestClient(app) as client:
            assert client.get("/ics/inexistant.ics").status_code == 404
    finally:
        app.dependency_overrides.clear()
