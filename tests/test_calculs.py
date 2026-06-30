"""Tests du calcul de la date limite de dénonciation (échéance − préavis)."""

from __future__ import annotations

from datetime import date

from contract_intelligence.domain import (
    Champ,
    Contrat,
    Partie,
    Preavis,
    UnitePreavis,
    calculer_date_limite_denonciation,
    date_limite_denonciation,
)


def _partie(raison: str) -> Partie:
    return Partie(raison_sociale=Champ[str](valeur=raison, confiance=1.0))


def test_preavis_en_jours() -> None:
    assert calculer_date_limite_denonciation(date(2025, 1, 15), 30, UnitePreavis.jours) == date(
        2024, 12, 16
    )


def test_preavis_en_mois_fin_de_mois() -> None:
    # 31 mars − 1 mois → 28 février (borné au dernier jour du mois cible).
    assert calculer_date_limite_denonciation(date(2025, 3, 31), 1, UnitePreavis.mois) == date(
        2025, 2, 28
    )


def test_preavis_en_mois_franchit_annee() -> None:
    assert calculer_date_limite_denonciation(date(2025, 1, 31), 1, UnitePreavis.mois) == date(
        2024, 12, 31
    )


def test_preavis_trois_mois() -> None:
    assert calculer_date_limite_denonciation(date(2025, 6, 30), 3, UnitePreavis.mois) == date(
        2025, 3, 30
    )


def test_depuis_contrat() -> None:
    contrat = Contrat(
        fournisseur=_partie("F"),
        client=_partie("C"),
        date_echeance=Champ[date](valeur=date(2025, 12, 31), confiance=0.95),
        preavis=Preavis(
            delai=Champ[int](valeur=3, confiance=0.9),
            unite=Champ[UnitePreavis](valeur=UnitePreavis.mois, confiance=0.9),
        ),
    )
    assert date_limite_denonciation(contrat) == date(2025, 9, 30)


def test_depuis_contrat_sans_echeance() -> None:
    contrat = Contrat(fournisseur=_partie("F"), client=_partie("C"))
    assert date_limite_denonciation(contrat) is None
