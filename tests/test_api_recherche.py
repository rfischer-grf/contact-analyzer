"""Tests d'API de la recherche facette + sémantique (#52).

Surcharge `get_principal`, `get_session_factory`, `get_vector_store`,
`get_embeddeur`. StaticPool pour partager la base SQLite in-memory entre threads.
"""

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
from contract_intelligence.api.routers.recherche import get_embeddeur, get_vector_store
from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.rag import FakeEmbeddeur, FakeVectorStore, projeter_contrat

MARKDOWN = (
    "# Article 1 - Objet\nFourniture de prestations.\n\n# Article 2 - Indexation\nIndice Syntec.\n"
)


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        s.add_all(
            [
                Contrat(
                    id=uuid.uuid4(),
                    tenant="acme",
                    reference="SYN",
                    indice="syntec",
                    fournisseur_siren="111111111",
                    date_echeance=date(2026, 9, 30),
                ),
                Contrat(
                    id=uuid.uuid4(),
                    tenant="acme",
                    reference="ILAT",
                    indice="ilat",
                    fournisseur_siren="222222222",
                    date_echeance=date(2027, 6, 30),
                ),
                Contrat(
                    id=uuid.uuid4(),
                    tenant="globex",
                    reference="GX",
                    indice="syntec",
                    date_echeance=date(2026, 1, 31),
                ),
            ]
        )
        s.commit()
    return f


def _overrides(factory, store, embeddeur, tenant: str = "acme") -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_principal] = lambda: Principal(
        sujet="alice", tenant=tenant, claims={}
    )
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embeddeur] = lambda: embeddeur


def test_facette_filtre_par_indice(factory) -> None:
    _overrides(factory, FakeVectorStore(), FakeEmbeddeur())
    try:
        with TestClient(app) as client:
            resp = client.get("/recherche/facette", params={"indice": "syntec"})
            assert resp.status_code == 200
            data = resp.json()
            assert [c["reference"] for c in data] == ["SYN"]
            assert data[0]["indice"] == "syntec"
            assert data[0]["date_echeance"] == "2026-09-30"
    finally:
        app.dependency_overrides.clear()


def test_facette_isole_le_tenant(factory) -> None:
    _overrides(factory, FakeVectorStore(), FakeEmbeddeur(), tenant="globex")
    try:
        with TestClient(app) as client:
            resp = client.get("/recherche/facette", params={"indice": "syntec"})
            assert resp.status_code == 200
            data = resp.json()
            assert [c["reference"] for c in data] == ["GX"]
    finally:
        app.dependency_overrides.clear()


def test_facette_sans_filtre(factory) -> None:
    _overrides(factory, FakeVectorStore(), FakeEmbeddeur())
    try:
        with TestClient(app) as client:
            resp = client.get("/recherche/facette")
            assert resp.status_code == 200
            assert {c["reference"] for c in resp.json()} == {"SYN", "ILAT"}
    finally:
        app.dependency_overrides.clear()


def test_facette_authentification_requise(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    try:
        with TestClient(app) as client:
            assert client.get("/recherche/facette").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_semantique_renvoie_chunks_du_tenant(factory) -> None:
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s:
        acme = s.query(Contrat).filter(Contrat.tenant == "acme").all()
        for c in acme:
            projeter_contrat(store, embeddeur, s, "acme", str(c.id), MARKDOWN)
        globex = s.query(Contrat).filter(Contrat.tenant == "globex").all()
        for c in globex:
            projeter_contrat(store, embeddeur, s, "globex", str(c.id), MARKDOWN)

    _overrides(factory, store, embeddeur)
    try:
        with TestClient(app) as client:
            resp = client.get("/recherche/semantique", params={"q": "indexation", "k": 10})
            assert resp.status_code == 200
            data = resp.json()
            assert data
            for chunk in data:
                assert chunk["metadata"]["tenant"] == "acme"
                assert "type_clause" in chunk
                assert "texte" in chunk
    finally:
        app.dependency_overrides.clear()


def test_semantique_q_obligatoire(factory) -> None:
    _overrides(factory, FakeVectorStore(), FakeEmbeddeur())
    try:
        with TestClient(app) as client:
            assert client.get("/recherche/semantique").status_code == 422
    finally:
        app.dependency_overrides.clear()
