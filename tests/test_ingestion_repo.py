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
    rattacher_au_parent,
    rejeter_metier,
)
from contract_intelligence.db.models import EvenementAudit


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


def _pieces_parent_et_avenant(s):
    """Crée un parent COMMITE (pièce d'origine) + un standalone A_VALIDER (avenant).

    Renvoie `(parent_id, standalone_id, doc_avenant_id)`.
    """
    parent_id = persister_extraction(
        s,
        tenant="acme",
        sha256="1" * 64,
        cle_s3=f"acme/{'1' * 64}",
        extraction=_extraction(),
        date_signature=date(2023, 1, 1),
    )
    marquer_etat(s, parent_id, "COMMITE")
    standalone_id = persister_extraction(
        s,
        tenant="acme",
        sha256="2" * 64,
        cle_s3=f"acme/{'2' * 64}",
        extraction=_extraction(),
        date_signature=date(2024, 6, 1),  # avenant signé après l'origine
    )
    doc_avenant = s.query(Document).filter(Document.contrat_id == standalone_id).one()
    return parent_id, standalone_id, doc_avenant.id


def test_rattacher_au_parent_deplace_le_document_et_supprime_orphelin(factory) -> None:
    """#33 : à la confirmation HITL, l'avenant rejoint le parent et l'orphelin disparaît."""
    with factory() as s:
        parent_id, standalone_id, doc_avenant_id = _pieces_parent_et_avenant(s)
        s.commit()

    with factory() as s:
        cible = rattacher_au_parent(s, contrat_id=standalone_id, parent_contrat_id=parent_id)
        s.commit()

    assert cible == parent_id
    with factory() as s:
        # Le contrat standalone (orphelin) a été supprimé.
        assert s.get(Contrat, standalone_id) is None
        # L'avenant pointe désormais le parent, avec un numéro d'avenant attribué.
        doc = s.get(Document, doc_avenant_id)
        assert doc.contrat_id == parent_id
        assert doc.numero_avenant == 1
        # Le parent porte bien ses deux pièces (origine + avenant).
        assert s.query(Document).filter(Document.contrat_id == parent_id).count() == 2
        # Traçabilité : un évènement de rattachement est consigné (§2).
        audits = (
            s.query(EvenementAudit)
            .filter(EvenementAudit.type_evenement == "AVENANT_RATTACHE")
            .all()
        )
        assert len(audits) == 1
        assert audits[0].payload["contrat_absorbe"] == str(standalone_id)


def test_rattacher_au_parent_idempotent_si_standalone_absent(factory) -> None:
    with factory() as s:
        parent_id, standalone_id, _ = _pieces_parent_et_avenant(s)
        rattacher_au_parent(s, contrat_id=standalone_id, parent_contrat_id=parent_id)
        s.commit()

    # Rejeu de l'activity : le standalone n'existe plus → renvoie le parent, no-op.
    with factory() as s:
        cible = rattacher_au_parent(s, contrat_id=standalone_id, parent_contrat_id=parent_id)
        s.commit()
    assert cible == parent_id


def test_rattacher_au_parent_parent_introuvable_leve(factory) -> None:
    import uuid

    with factory() as s:
        _, standalone_id, _ = _pieces_parent_et_avenant(s)
        with pytest.raises(ValueError, match="parent introuvable"):
            rattacher_au_parent(s, contrat_id=standalone_id, parent_contrat_id=uuid.uuid4())
