"""Tests de la recherche facette (SQL) vs sémantique (vectoriel) + réconciliation.

Garde-fou (§6) : facette = SQL `WHERE`, sémantique = vectoriel borné au tenant.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.rag import (
    FakeEmbeddeur,
    FakeVectorStore,
    projeter_contrat,
    recherche_facette,
    recherche_semantique,
    reconcilier,
)

MARKDOWN = (
    "# Article 1 - Objet\nFourniture de prestations.\n\n# Article 2 - Indexation\nIndice Syntec.\n"
)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
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
                    fournisseur_siren="333333333",
                    date_echeance=date(2026, 1, 31),
                ),
            ]
        )
        s.commit()
    return f


def test_facette_filtre_par_indice(factory) -> None:
    with factory() as s:
        res = recherche_facette(s, "acme", indice="syntec")
    assert [c.reference for c in res] == ["SYN"]


def test_facette_filtre_par_echeance(factory) -> None:
    with factory() as s:
        res = recherche_facette(s, "acme", echeance_avant=date(2026, 12, 31))
    assert [c.reference for c in res] == ["SYN"]


def test_facette_filtre_par_fournisseur(factory) -> None:
    with factory() as s:
        res = recherche_facette(s, "acme", fournisseur_siren="222222222")
    assert [c.reference for c in res] == ["ILAT"]


def test_facette_isole_le_tenant(factory) -> None:
    # globex a aussi un contrat syntec mais acme ne le voit pas.
    with factory() as s:
        res = recherche_facette(s, "acme", indice="syntec")
    assert all(c.tenant == "acme" for c in res)
    assert "GX" not in [c.reference for c in res]


def test_semantique_renvoie_chunks_du_bon_tenant(factory) -> None:
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s:
        for c in recherche_facette(s, "acme"):
            projeter_contrat(store, embeddeur, s, "acme", str(c.id), MARKDOWN)
        for c in recherche_facette(s, "globex"):
            projeter_contrat(store, embeddeur, s, "globex", str(c.id), MARKDOWN)

    chunks = recherche_semantique(store, embeddeur, "acme", "indexation syntec", k=10)
    assert chunks
    assert all(c.tenant == "acme" for c in chunks)


def test_semantique_respecte_k(factory) -> None:
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s:
        for c in recherche_facette(s, "acme"):
            projeter_contrat(store, embeddeur, s, "acme", str(c.id), MARKDOWN)
    chunks = recherche_semantique(store, embeddeur, "acme", "objet", k=2)
    assert len(chunks) == 2


def test_reconciliation_detecte_manquants_et_orphelins(factory) -> None:
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s:
        contrats = recherche_facette(s, "acme")
        # On ne projette qu'un seul contrat sur deux → l'autre est manquant.
        projeter_contrat(store, embeddeur, s, "acme", str(contrats[0].id), MARKDOWN)
        # Un id orphelin présent dans le store mais absent en base.
        store.upsert("acme", "00000000-0000-0000-0000-000000000000", [])

        diff = reconcilier(s, store, "acme")

    assert str(contrats[1].id) in diff["manquants_dans_store"]
    assert "00000000-0000-0000-0000-000000000000" in diff["orphelins_dans_store"]
    assert str(contrats[0].id) not in diff["manquants_dans_store"]
