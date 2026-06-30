"""Tests du moteur de révision tarifaire — purs (§2.5)."""

from __future__ import annotations

from datetime import date

import pytest

from contract_intelligence.indexation import (
    COEFFICIENT_RACCORD_SYNTEC,
    coefficient_raccord_syntec,
    reviser,
)


def test_reviser_simple() -> None:
    assert reviser(1000.0, 100.0, 110.0) == pytest.approx(1100.0)


def test_reviser_part_fixe() -> None:
    # a = 0,5 → facteur = 0,5 + 0,5 × 1,1 = 1,05
    assert reviser(1000.0, 100.0, 110.0, part_fixe=0.5) == pytest.approx(1050.0)


def test_reviser_bidirectionnel_baisse() -> None:
    # §7 : S1 < S0 → le prix baisse (aucune borne « hausse seule »).
    p1 = reviser(1000.0, 110.0, 100.0)
    assert p1 < 1000.0
    assert p1 == pytest.approx(1000.0 * 100.0 / 110.0)


def test_reviser_s0_nul() -> None:
    with pytest.raises(ValueError):
        reviser(1000.0, 0.0, 110.0)


def test_reviser_part_fixe_hors_bornes() -> None:
    with pytest.raises(ValueError):
        reviser(1000.0, 100.0, 110.0, part_fixe=1.5)


def test_coefficient_raccord_syntec() -> None:
    assert coefficient_raccord_syntec("syntec", date(2020, 1, 1)) == COEFFICIENT_RACCORD_SYNTEC
    assert coefficient_raccord_syntec("syntec", date(2023, 1, 1)) == 1.0
    # Le raccord ne concerne que Syntec.
    assert coefficient_raccord_syntec("ilat", date(2020, 1, 1)) == 1.0
    assert coefficient_raccord_syntec("syntec", None) == 1.0
