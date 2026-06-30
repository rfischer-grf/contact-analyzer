"""Test de l'endpoint tableau de bord (KPIs)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contract_intelligence.api.app import app
from contract_intelligence.api.auth import Principal, get_principal
from contract_intelligence.api.deps import get_session_factory
from contract_intelligence.db import Base, Contrat, make_sessionmaker

REF = date(2026, 1, 1)


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                indice="ilat",
                montant=1000.0,
                date_limite_denonciation=REF + timedelta(days=90),
            )
        )
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                indice="syntec",
                montant=500.0,
                date_limite_denonciation=REF + timedelta(days=30),
            )
        )
        s.add(Contrat(id=uuid.uuid4(), tenant="globex", indice="ilc", montant=9999.0))
        s.commit()
    return f


@pytest.fixture(autouse=True)
def _principal_acme():
    app.dependency_overrides[get_principal] = lambda: Principal("alice", "acme", {})
    yield
    app.dependency_overrides.clear()


def test_tableau_de_bord(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        body = client.get("/tableau-de-bord", params={"aujourd_hui": "2026-01-01"}).json()
    assert body["nb_contrats"] == 2  # tenant acme seulement
    assert body["montant_total"] == pytest.approx(1500.0)
    assert body["par_indice"] == {"ilat": 1, "syntec": 1}
    assert body["alertes"]["90"] == 1
    assert body["alertes"]["30"] == 1
    assert len(body["prochaines_echeances"]) == 2
    assert body["prochaines_echeances"][0]["jours_restants"] == 30  # trié
