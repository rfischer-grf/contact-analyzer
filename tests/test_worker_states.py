"""Tests de l'enum d'états de la saga (pur, sans dépendance temporalio)."""

from __future__ import annotations

from contract_intelligence.worker.states import ETATS_TERMINAUX, EtatIngestion


def test_etats_terminaux() -> None:
    assert ETATS_TERMINAUX == {
        EtatIngestion.COMMITE,
        EtatIngestion.REJETE_TECHNIQUE,
        EtatIngestion.REJETE_METIER,
    }


def test_etats_attendus_presents() -> None:
    for nom in ("RECU", "A_VALIDER", "VALIDE", "COMMITE"):
        assert nom in EtatIngestion.__members__
