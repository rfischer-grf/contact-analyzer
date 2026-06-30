"""Tests du dédoublonnage par SHA256 (#15, spec §2.1) sur SQLite en mémoire."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Document, make_sessionmaker
from contract_intelligence.ingestion import document_existe

SHA_A = "a" * 64
SHA_B = "b" * 64


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def _inserer(factory, *, tenant: str, sha256: str) -> None:
    with factory() as session, session.begin():
        session.add(
            Document(
                tenant=tenant,
                sha256=sha256,
                cle_s3=f"{tenant}/{sha256}.pdf",
                date_signature=date(2026, 1, 1),
            )
        )


def test_document_absent_renvoie_false(factory):
    with factory() as session:
        assert document_existe(session, "acme", SHA_A) is False


def test_document_present_renvoie_true(factory):
    _inserer(factory, tenant="acme", sha256=SHA_A)
    with factory() as session:
        assert document_existe(session, "acme", SHA_A) is True


def test_dedup_borne_par_tenant(factory):
    # Même SHA256, autre tenant → considéré absent (isolation, §7).
    _inserer(factory, tenant="acme", sha256=SHA_A)
    with factory() as session:
        assert document_existe(session, "globex", SHA_A) is False


def test_dedup_borne_par_sha(factory):
    # Même tenant, autre SHA256 → absent.
    _inserer(factory, tenant="acme", sha256=SHA_A)
    with factory() as session:
        assert document_existe(session, "acme", SHA_B) is False
