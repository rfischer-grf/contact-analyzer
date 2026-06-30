"""Tests des modèles du domaine (§3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contract_intelligence.domain import (
    Champ,
    Contrat,
    Indice,
    Partie,
    Provenance,
)


def _partie(raison: str) -> Partie:
    return Partie(raison_sociale=Champ[str](valeur=raison, confiance=0.99))


def test_champ_porte_valeur_confiance_provenance() -> None:
    champ = Champ[str](
        valeur="ACME SAS",
        confiance=0.92,
        source=Provenance(page=1, bbox=(0.1, 0.2, 0.3, 0.4), extrait="ACME SAS"),
    )
    assert champ.valeur == "ACME SAS"
    assert champ.source is not None and champ.source.page == 1


def test_confiance_hors_bornes_rejetee() -> None:
    with pytest.raises(ValidationError):
        Champ[str](valeur="x", confiance=1.5)


def test_contrat_roundtrip() -> None:
    contrat = Contrat(
        fournisseur=_partie("Fournisseur SAS"),
        client=_partie("Client SA"),
        indexation=None,
    )
    dump = contrat.model_dump()
    rebuilt = Contrat.model_validate(dump)
    assert rebuilt.fournisseur.raison_sociale.valeur == "Fournisseur SAS"


def test_indice_enum_valeurs() -> None:
    assert {i.value for i in Indice} == {
        "syntec",
        "ilat",
        "ilc",
        "icc",
        "insee_autre",
        "aucun",
    }
