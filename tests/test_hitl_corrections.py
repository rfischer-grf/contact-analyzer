"""Tests des corrections HITL → gold set (#37) sur SQLite."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Correction, make_sessionmaker
from contract_intelligence.hitl import enregistrer_correction, gold_set


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def test_enregistrer_correction_persiste(factory) -> None:
    cid = uuid.uuid4()
    with factory() as s:
        correction = enregistrer_correction(
            s,
            tenant="acme",
            contrat_id=cid,
            champ="preavis.delai",
            ancienne_valeur="30",
            nouvelle_valeur="60",
            acteur="alice",
        )
        s.commit()
        assert isinstance(correction, Correction)
        assert correction.id is not None
        assert correction.horodatage is not None
        # contrat_id normalisé en chaîne.
        assert correction.contrat_id == str(cid)
        assert correction.tenant == "acme"
        assert correction.acteur == "alice"


def test_enregistrer_correction_valeurs_nulles(factory) -> None:
    with factory() as s:
        correction = enregistrer_correction(
            s,
            tenant="acme",
            contrat_id="ref-libre",
            champ="objet",
            ancienne_valeur=None,
            nouvelle_valeur="Maintenance",
            acteur=None,
        )
        s.commit()
        assert correction.ancienne_valeur is None
        assert correction.acteur is None
        assert correction.contrat_id == "ref-libre"


def test_gold_set_par_tenant(factory) -> None:
    with factory() as s:
        enregistrer_correction(s, "acme", uuid.uuid4(), "montant", "1000", "1200", "alice")
        enregistrer_correction(s, "acme", uuid.uuid4(), "devise", "USD", "EUR", "bob")
        enregistrer_correction(s, "globex", uuid.uuid4(), "montant", "5", "6", "carol")
        s.commit()

    with factory() as s:
        acme = gold_set(s, "acme")
        globex = gold_set(s, "globex")
        vide = gold_set(s, "inconnu")

    assert {c.champ for c in acme} == {"montant", "devise"}
    assert all(c.tenant == "acme" for c in acme)
    assert len(globex) == 1
    assert globex[0].tenant == "globex"
    assert vide == []
