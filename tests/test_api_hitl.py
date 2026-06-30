"""Tests d'API HITL (#35, #36, #37) : valider/rejeter (signal injecté), corrections,
champs à revoir. Base SQLite in-memory partagée entre threads (StaticPool)."""

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
from contract_intelligence.api.routers.hitl import get_signal_sender
from contract_intelligence.db import Base, Contrat, Correction, Document, make_sessionmaker
from contract_intelligence.hitl import gold_set


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


@pytest.fixture(autouse=True)
def _principal():
    app.dependency_overrides[get_principal] = lambda: Principal(
        sujet="alice", tenant="acme", claims={}
    )
    yield
    app.dependency_overrides.clear()


def test_valider_emet_signal() -> None:
    appels: list[tuple[str, str]] = []

    async def double(workflow_id: str, decision: str) -> None:
        appels.append((workflow_id, decision))

    app.dependency_overrides[get_signal_sender] = lambda: double
    with TestClient(app) as client:
        resp = client.post("/hitl/contrats/wf-123/valider")
    assert resp.status_code == 200
    assert resp.json() == {"statut": "signal_emis", "decision": "valider"}
    assert appels == [("wf-123", "valider")]


def test_rejeter_emet_signal() -> None:
    appels: list[tuple[str, str]] = []

    async def double(workflow_id: str, decision: str) -> None:
        appels.append((workflow_id, decision))

    app.dependency_overrides[get_signal_sender] = lambda: double
    with TestClient(app) as client:
        resp = client.post("/hitl/contrats/wf-9/rejeter")
    assert resp.status_code == 200
    assert resp.json() == {"statut": "signal_emis", "decision": "rejeter"}
    assert appels == [("wf-9", "rejeter")]


def test_signal_workflow_injoignable() -> None:
    async def double(workflow_id: str, decision: str) -> None:
        raise RuntimeError("injoignable")

    app.dependency_overrides[get_signal_sender] = lambda: double
    with TestClient(app) as client:
        resp = client.post("/hitl/contrats/wf-x/valider")
    assert resp.status_code == 404


def test_enregistrer_corrections(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    corps = {
        "corrections": [
            {"champ": "preavis.delai", "ancienne_valeur": "30", "nouvelle_valeur": "60"},
            {"champ": "montant", "ancienne_valeur": None, "nouvelle_valeur": "1200"},
        ]
    }
    with TestClient(app) as client:
        resp = client.post("/hitl/contrats/c-1/corrections", json=corps)
    assert resp.status_code == 201
    assert resp.json() == {"enregistrees": 2}

    with factory() as s:
        corrections = gold_set(s, "acme")
    assert {c.champ for c in corrections} == {"preavis.delai", "montant"}
    assert all(c.tenant == "acme" and c.acteur == "alice" for c in corrections)
    assert all(isinstance(c, Correction) for c in corrections)


def _extraction(confiance_echeance: float) -> dict:
    """Extraction minimale (`domain.Contrat` sérialisé) : champs `Champ` imbriqués."""
    return {
        "fournisseur": {"raison_sociale": {"valeur": "F", "confiance": 1.0, "source": None}},
        "client": {"raison_sociale": {"valeur": "C", "confiance": 1.0, "source": None}},
        "date_echeance": {"valeur": "2025-12-31", "confiance": confiance_echeance, "source": None},
        "preavis": {
            "delai": {"valeur": 3, "confiance": 0.5, "source": None},
            "unite": {"valeur": "mois", "confiance": 0.95, "source": None},
        },
    }


def test_champs_a_revoir_endpoint(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    cid = uuid.uuid4()
    with factory() as s:
        s.add(Contrat(id=cid, tenant="acme"))
        s.add(
            Document(
                tenant="acme",
                sha256="a" * 64,
                cle_s3=f"acme/{'a' * 64}",
                date_signature=date(2023, 1, 1),
                contrat_id=cid,
                extraction=_extraction(confiance_echeance=0.6),
            )
        )
        s.commit()

    with TestClient(app) as client:
        resp = client.get(f"/hitl/contrats/{cid}/champs-a-revoir")
    assert resp.status_code == 200
    # date_echeance (0.6) et preavis.delai (0.5) sous 0.8 ; le reste fiable.
    assert resp.json() == {"champs": ["date_echeance", "preavis.delai"]}


def test_champs_a_revoir_sans_extraction(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    cid = uuid.uuid4()
    with factory() as s:
        s.add(Contrat(id=cid, tenant="acme"))
        s.commit()

    with TestClient(app) as client:
        resp = client.get(f"/hitl/contrats/{cid}/champs-a-revoir")
    assert resp.status_code == 200
    assert resp.json() == {"champs": []}
