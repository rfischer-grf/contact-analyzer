"""Tests de la persistance d'ingestion (`db.ingestion_repo`) sur SQLite.

Couvre la distinction document/contrat (§3.1) et le gate HITL (§7) : une pièce
versée crée un `Document` (extraction JSON) + un `Contrat(etat="A_VALIDER")`,
idempotent sur `(tenant, sha256)`. `marquer_etat`/`rejeter_metier` pilotent l'état.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Contrat, Document, make_sessionmaker
from contract_intelligence.db.ingestion_repo import (
    marquer_etat,
    persister_extraction,
    rejeter_metier,
)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def _extraction() -> dict:
    """Extraction sérialisée minimale (wrapper `Champ` → `{"valeur": ...}`)."""
    return {
        "fournisseur": {"raison_sociale": {"valeur": "ACME", "confiance": 0.99}},
        "client": {"raison_sociale": {"valeur": "RF", "confiance": 0.99}},
        "objet": {"valeur": "maintenance", "confiance": 0.9},
    }


def test_persister_extraction_cree_document_et_contrat_a_valider(factory) -> None:
    with factory() as s:
        contrat_id = persister_extraction(
            s,
            tenant="acme",
            sha256="a" * 64,
            cle_s3=f"acme/{'a' * 64}",
            extraction=_extraction(),
            date_signature=date(2024, 1, 1),
        )
        s.commit()

    with factory() as s:
        contrat = s.get(Contrat, contrat_id)
        assert contrat is not None
        assert contrat.tenant == "acme"
        # Gate HITL : le contrat n'entre nulle part avant validation (§7).
        assert contrat.etat == "A_VALIDER"

        documents = s.query(Document).filter(Document.contrat_id == contrat_id).all()
        assert len(documents) == 1
        doc = documents[0]
        assert doc.sha256 == "a" * 64
        assert doc.cle_s3 == f"acme/{'a' * 64}"
        assert doc.date_signature == date(2024, 1, 1)
        assert doc.extraction == _extraction()
        assert doc.contrat_id == contrat_id


def test_persister_extraction_idempotent_sur_sha256(factory) -> None:
    with factory() as s:
        premier = persister_extraction(
            s,
            tenant="acme",
            sha256="b" * 64,
            cle_s3=f"acme/{'b' * 64}",
            extraction=_extraction(),
            date_signature=date(2024, 2, 1),
        )
        s.commit()

    # Rejeu de la même pièce : pas de doublon, même contrat, extraction rafraîchie.
    with factory() as s:
        maj = dict(_extraction())
        maj["objet"] = {"valeur": "maintenance corrigée", "confiance": 0.95}
        second = persister_extraction(
            s,
            tenant="acme",
            sha256="b" * 64,
            cle_s3=f"acme/{'b' * 64}",
            extraction=maj,
            date_signature=date(2024, 2, 1),
        )
        s.commit()

    assert premier == second
    with factory() as s:
        assert s.query(Document).count() == 1
        assert s.query(Contrat).count() == 1
        doc = s.query(Document).filter(Document.sha256 == "b" * 64).one()
        assert doc.extraction["objet"]["valeur"] == "maintenance corrigée"


def test_persister_extraction_porte_numero_avenant_et_reference(factory) -> None:
    with factory() as s:
        contrat_id = persister_extraction(
            s,
            tenant="acme",
            sha256="c" * 64,
            cle_s3=f"acme/{'c' * 64}",
            extraction=_extraction(),
            date_signature=date(2025, 3, 1),
            numero_avenant=2,
            reference="REF-2025-007",
        )
        s.commit()

    with factory() as s:
        doc = s.query(Document).filter(Document.contrat_id == contrat_id).one()
        assert doc.numero_avenant == 2
        assert doc.reference == "REF-2025-007"


def test_marquer_etat_met_a_jour_le_contrat(factory) -> None:
    with factory() as s:
        contrat_id = persister_extraction(
            s,
            tenant="acme",
            sha256="d" * 64,
            cle_s3=f"acme/{'d' * 64}",
            extraction=_extraction(),
            date_signature=date(2024, 1, 1),
        )
        s.commit()

    with factory() as s:
        marquer_etat(s, contrat_id, "COMMITE")
        s.commit()

    with factory() as s:
        assert s.get(Contrat, contrat_id).etat == "COMMITE"


def test_rejeter_metier_marque_rejete(factory) -> None:
    with factory() as s:
        contrat_id = persister_extraction(
            s,
            tenant="acme",
            sha256="e" * 64,
            cle_s3=f"acme/{'e' * 64}",
            extraction=_extraction(),
            date_signature=date(2024, 1, 1),
        )
        s.commit()

    with factory() as s:
        rejeter_metier(s, contrat_id)
        s.commit()

    with factory() as s:
        assert s.get(Contrat, contrat_id).etat == "REJETE_METIER"


def test_marquer_etat_contrat_introuvable_leve(factory) -> None:
    import uuid

    with factory() as s, pytest.raises(ValueError, match="introuvable"):
        marquer_etat(s, uuid.uuid4(), "COMMITE")
