"""Tests de la projection tarifaire d'un contrat (SQLite)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from contract_intelligence.db import Base, Contrat, make_sessionmaker
from contract_intelligence.indexation import charger_fixtures, projeter_tarif
from contract_intelligence.indexation.moteur import COEFFICIENT_RACCORD_SYNTEC

FIXTURES = Path(__file__).resolve().parents[1] / "infra" / "fixtures" / "series_indices.json"


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        charger_fixtures(s, FIXTURES)
        s.commit()
    return f


def test_projection_ilat(factory) -> None:
    cid = uuid.uuid4()
    with factory() as s:
        s.add(
            Contrat(
                id=cid,
                tenant="acme",
                indice="ilat",
                indice_base_valeur=118.0,
                indice_base_periode="2022-03",
                date_acte_reference=date(2022, 6, 1),
                montant=1000.0,
            )
        )
        s.commit()

    with factory() as s:
        contrat = s.get(Contrat, cid)
        res = projeter_tarif(s, contrat, date(2024, 6, 1))
        # S1 = ILAT 2024-03 = 130 ; S0 = 118 ; pas de raccord (≠ Syntec).
        assert res.coefficient_raccord == 1.0
        assert res.s1 == pytest.approx(130.0)
        assert res.p1 == pytest.approx(1000.0 * 130.0 / 118.0)


def test_projection_syntec_avec_raccord(factory) -> None:
    cid = uuid.uuid4()
    with factory() as s:
        s.add(
            Contrat(
                id=cid,
                tenant="acme",
                indice="syntec",
                indice_base_valeur=110.0,
                indice_base_periode="2021-01",
                date_acte_reference=date(2020, 1, 1),  # < août 2022 → raccord
                montant=1000.0,
            )
        )
        s.commit()

    with factory() as s:
        contrat = s.get(Contrat, cid)
        res = projeter_tarif(s, contrat, date(2024, 1, 1))
        assert res.coefficient_raccord == COEFFICIENT_RACCORD_SYNTEC
        s0_raccorde = 110.0 * COEFFICIENT_RACCORD_SYNTEC
        assert res.s0 == pytest.approx(s0_raccorde)
        assert res.s1 == pytest.approx(128.0)  # Syntec 2024-01
        assert res.p1 == pytest.approx(1000.0 * 128.0 / s0_raccorde)


def test_projection_sans_indexation(factory) -> None:
    cid = uuid.uuid4()
    with factory() as s:
        s.add(Contrat(id=cid, tenant="acme", indice="aucun", montant=1000.0))
        s.commit()
    with factory() as s:
        contrat = s.get(Contrat, cid)
        with pytest.raises(ValueError):
            projeter_tarif(s, contrat, date(2024, 1, 1))
