"""Tests des séries d'indices + chargement de fixtures (SQLite)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, make_sessionmaker
from contract_intelligence.db.series import dernier_indice_a_date, upsert_serie
from contract_intelligence.indexation import charger_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "infra" / "fixtures" / "series_indices.json"


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def test_dernier_indice_a_date(factory) -> None:
    with factory() as s:
        upsert_serie(s, "syntec", "2022-01", 115.0)
        upsert_serie(s, "syntec", "2023-01", 122.0)
        s.commit()

    with factory() as s:
        # À mi-2023, le dernier indice connu est celui de 2023-01.
        assert dernier_indice_a_date(s, "syntec", date(2023, 6, 30)) == ("2023-01", 122.0)
        # Avant toute publication → None.
        assert dernier_indice_a_date(s, "syntec", date(2021, 1, 1)) is None


def test_upsert_idempotent(factory) -> None:
    with factory() as s:
        upsert_serie(s, "ilat", "2024-03", 130.0)
        upsert_serie(s, "ilat", "2024-03", 131.0, source="correction")
        s.commit()

    with factory() as s:
        assert dernier_indice_a_date(s, "ilat", date(2024, 4, 1)) == ("2024-03", 131.0)


def test_charger_fixtures(factory) -> None:
    with factory() as s:
        n = charger_fixtures(s, FIXTURES)
        s.commit()
    assert n >= 4
    with factory() as s:
        # La clé de métadonnées "_comment" est ignorée.
        assert dernier_indice_a_date(s, "syntec", date(2024, 6, 1)) == ("2024-01", 128.0)
