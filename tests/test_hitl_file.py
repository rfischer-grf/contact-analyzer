"""Tests de la file de revue HITL globale (#35) : contrats `A_VALIDER` du tenant.

- Logique pure `file_de_revue` (SQLite) : périmètre tenant + état + ordre.
- Endpoint `GET /hitl/file` (TestClient + overrides, StaticPool partagé entre threads).
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
from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.hitl import file_de_revue


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


def _peupler(factory) -> tuple[uuid.UUID, uuid.UUID]:
    """Deux contrats A_VALIDER (acme) + un COMMITE (acme) + un A_VALIDER (autre tenant).

    Renvoie les ids des deux contrats A_VALIDER d'acme, dans l'ordre d'échéance attendu.
    """
    tot = uuid.uuid4()  # échéance la plus proche
    tard = uuid.uuid4()  # échéance la plus lointaine
    with factory() as s:
        s.add(
            Contrat(
                id=tard,
                tenant="acme",
                etat="A_VALIDER",
                reference="C-2",
                objet="Maintenance",
                date_echeance=date(2026, 12, 31),
                fournisseur_siren="111111111",
            )
        )
        s.add(
            Contrat(
                id=tot,
                tenant="acme",
                etat="A_VALIDER",
                reference="C-1",
                objet="Hébergement",
                date_echeance=date(2026, 9, 30),
                fournisseur_siren="222222222",
            )
        )
        # Bruit qui ne doit PAS apparaître : commité (acme) + A_VALIDER d'un autre tenant.
        s.add(Contrat(id=uuid.uuid4(), tenant="acme", etat="COMMITE", reference="C-OK"))
        s.add(Contrat(id=uuid.uuid4(), tenant="autre", etat="A_VALIDER", reference="X-1"))
        s.commit()
    return tot, tard


def test_file_de_revue_perimetre_et_ordre(factory) -> None:
    tot, tard = _peupler(factory)
    with factory() as s:
        resumes = file_de_revue(s, "acme")

    # Seuls les deux A_VALIDER d'acme, échéance croissante (la plus proche d'abord).
    assert [r.id for r in resumes] == [str(tot), str(tard)]
    assert [r.reference for r in resumes] == ["C-1", "C-2"]
    assert resumes[0].objet == "Hébergement"
    assert resumes[0].date_echeance == date(2026, 9, 30)
    assert resumes[0].fournisseur_siren == "222222222"


def test_file_de_revue_autre_tenant_vide(factory) -> None:
    _peupler(factory)
    with factory() as s:
        # Le tenant « autre » n'a qu'un seul contrat A_VALIDER.
        assert [r.reference for r in file_de_revue(s, "autre")] == ["X-1"]
        # Un tenant inconnu ne voit rien.
        assert file_de_revue(s, "inconnu") == []


def test_endpoint_file_de_revue(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    tot, tard = _peupler(factory)

    with TestClient(app) as client:
        resp = client.get("/hitl/file")

    assert resp.status_code == 200
    corps = resp.json()
    assert [item["id"] for item in corps] == [str(tot), str(tard)]
    assert [item["reference"] for item in corps] == ["C-1", "C-2"]
    assert corps[0] == {
        "id": str(tot),
        "reference": "C-1",
        "objet": "Hébergement",
        "date_echeance": "2026-09-30",
        "fournisseur_siren": "222222222",
    }


def test_endpoint_file_de_revue_vide(factory) -> None:
    app.dependency_overrides[get_session_factory] = lambda: factory
    # Aucun contrat A_VALIDER pour acme.
    with factory() as s:
        s.add(Contrat(id=uuid.uuid4(), tenant="acme", etat="COMMITE", reference="C-OK"))
        s.commit()

    with TestClient(app) as client:
        resp = client.get("/hitl/file")
    assert resp.status_code == 200
    assert resp.json() == []
