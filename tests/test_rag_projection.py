"""Tests de la projection vers le vector store (#50, #48, #49).

- idempotence sur contrat_id (re-projeter ne crée pas de doublon) ;
- la suppression isole le tenant ;
- le FakeVectorStore n'expose pas un tenant à un autre.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.rag import FakeEmbeddeur, FakeVectorStore, projeter_contrat

MARKDOWN = """# Contrat
Préambule.

## Article 1 - Objet
Fourniture de prestations informatiques.

## Article 2 - Durée
Conclu pour 36 mois, tacite reconduction.
"""


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    return f


def _ajouter_contrat(factory, tenant: str) -> str:
    cid = uuid.uuid4()
    with factory() as s:
        s.add(
            Contrat(
                id=cid,
                tenant=tenant,
                reference="C-1",
                fournisseur_siren="123456789",
                objet="prestations",
                date_echeance=date(2026, 12, 31),
            )
        )
        s.commit()
    return str(cid)


def test_projection_cree_chunks_et_metadonnees(factory) -> None:
    cid = _ajouter_contrat(factory, "acme")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()

    with factory() as s:
        n = projeter_contrat(store, embeddeur, s, "acme", cid, MARKDOWN)

    assert n == 3
    chunks = store.rechercher("acme", embeddeur.vectoriser(["objet"])[0], k=10)
    assert {c.type_clause for c in chunks} == {"Contrat", "Article 1 - Objet", "Article 2 - Durée"}
    # Métadonnées de filtrage RAG présentes sur chaque chunk.
    for c in chunks:
        assert c.metadata["contrat_id"] == cid
        assert c.metadata["tenant"] == "acme"
        assert c.metadata["fournisseur_siren"] == "123456789"
        assert c.metadata["date_echeance"] == "2026-12-31"
        assert c.metadata["type_clause"] == c.type_clause
        assert c.vecteur is not None


def test_reprojection_idempotente(factory) -> None:
    cid = _ajouter_contrat(factory, "acme")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()

    with factory() as s:
        projeter_contrat(store, embeddeur, s, "acme", cid, MARKDOWN)
        projeter_contrat(store, embeddeur, s, "acme", cid, MARKDOWN)

    # delete-then-insert : pas de doublon après re-projection.
    chunks = store.rechercher("acme", embeddeur.vectoriser(["x"])[0], k=100)
    assert len(chunks) == 3
    assert store.contrat_ids("acme") == {cid}


def test_suppression_isole_le_tenant(factory) -> None:
    cid_acme = _ajouter_contrat(factory, "acme")
    cid_globex = _ajouter_contrat(factory, "globex")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()

    with factory() as s:
        projeter_contrat(store, embeddeur, s, "acme", cid_acme, MARKDOWN)
        projeter_contrat(store, embeddeur, s, "globex", cid_globex, MARKDOWN)

    store.supprimer("acme", cid_acme)

    assert store.contrat_ids("acme") == set()
    # La suppression chez acme n'affecte pas globex.
    assert store.contrat_ids("globex") == {cid_globex}


def test_fake_store_isole_les_tenants(factory) -> None:
    cid_acme = _ajouter_contrat(factory, "acme")
    cid_globex = _ajouter_contrat(factory, "globex")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()

    with factory() as s:
        projeter_contrat(store, embeddeur, s, "acme", cid_acme, MARKDOWN)
        projeter_contrat(store, embeddeur, s, "globex", cid_globex, MARKDOWN)

    vecteur = embeddeur.vectoriser(["objet"])[0]
    # globex ne voit jamais un chunk d'acme.
    chunks_globex = store.rechercher("globex", vecteur, k=100)
    assert chunks_globex
    assert all(c.tenant == "globex" and c.contrat_id == cid_globex for c in chunks_globex)


def test_projection_rejette_mauvais_tenant(factory) -> None:
    cid = _ajouter_contrat(factory, "acme")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s, pytest.raises(ValueError):
        projeter_contrat(store, embeddeur, s, "globex", cid, MARKDOWN)


def test_projection_markdown_vide_purge(factory) -> None:
    cid = _ajouter_contrat(factory, "acme")
    store = FakeVectorStore()
    embeddeur = FakeEmbeddeur()
    with factory() as s:
        projeter_contrat(store, embeddeur, s, "acme", cid, MARKDOWN)
        n = projeter_contrat(store, embeddeur, s, "acme", cid, "")
    assert n == 0
    assert store.contrat_ids("acme") == set()
