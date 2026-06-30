"""Tests des endpoints contrats + projection (front Clausio)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from contract_intelligence.api.app import app
from contract_intelligence.api.auth import Principal, get_principal
from contract_intelligence.api.deps import get_session_factory
from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.indexation import charger_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "infra" / "fixtures" / "series_indices.json"
ACME = uuid.uuid4()


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        charger_fixtures(s, FIXTURES)
        s.add(
            Contrat(
                id=ACME,
                tenant="acme",
                reference="C-1",
                indice="ilat",
                indice_base_valeur=118.0,
                indice_base_periode="2022-03",
                date_acte_reference=date(2022, 6, 1),
                montant=1000.0,
                date_echeance=date(2025, 12, 31),
                date_limite_denonciation=date(2025, 9, 30),
            )
        )
        s.add(Contrat(id=uuid.uuid4(), tenant="globex", reference="G-1", indice="syntec"))
        s.commit()
    return f


@pytest.fixture(autouse=True)
def _principal_acme():
    app.dependency_overrides[get_principal] = lambda: Principal("alice", "acme", {})
    yield
    app.dependency_overrides.clear()


def test_lister_filtre_tenant_et_indice(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        tous = client.get("/contrats").json()
        assert {c["reference"] for c in tous} == {"C-1"}  # globex non visible
        filtre = client.get("/contrats", params={"indice": "syntec"}).json()
        assert filtre == []


def test_detail_et_404(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        d = client.get(f"/contrats/{ACME}")
        assert d.status_code == 200
        assert d.json()["reference"] == "C-1"
        assert d.json()["bidirectionnelle"] is True
        assert client.get(f"/contrats/{uuid.uuid4()}").status_code == 404


def test_projection(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        resp = client.post(f"/contrats/{ACME}/projection", json={"date_revision": "2024-06-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["s1"] == pytest.approx(130.0)  # ILAT 2024-03
    assert body["p1"] == pytest.approx(1000.0 * 130.0 / 118.0)
