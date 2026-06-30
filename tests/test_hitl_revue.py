"""Tests purs de la file de revue HITL (#35) — champs sous le seuil de confiance."""

from __future__ import annotations

from contract_intelligence.hitl import champs_a_revoir, champs_a_revoir_par_seuils


def test_champs_a_revoir_sous_le_seuil() -> None:
    confiances = {"montant": 0.95, "preavis": 0.5, "date_echeance": 0.79}
    assert champs_a_revoir(confiances) == ["date_echeance", "preavis"]


def test_champs_a_revoir_seuil_exact_non_retenu() -> None:
    # Confiance == seuil → suffisamment fiable, non retenue.
    assert champs_a_revoir({"objet": 0.8}, seuil=0.8) == []


def test_champs_a_revoir_tries() -> None:
    confiances = {"z": 0.1, "a": 0.2, "m": 0.3}
    assert champs_a_revoir(confiances) == ["a", "m", "z"]


def test_champs_a_revoir_dict_vide() -> None:
    assert champs_a_revoir({}) == []


def test_champs_a_revoir_seuil_personnalise() -> None:
    confiances = {"montant": 0.85, "preavis": 0.85}
    assert champs_a_revoir(confiances, seuil=0.9) == ["montant", "preavis"]
    assert champs_a_revoir(confiances, seuil=0.8) == []


def test_champs_a_revoir_par_seuils_defaut() -> None:
    # `preavis` critique (seuil 0.95) ; les autres au défaut 0.8.
    confiances = {"preavis": 0.9, "montant": 0.85, "objet": 0.7}
    seuils = {"preavis": 0.95}
    assert champs_a_revoir_par_seuils(confiances, seuils) == ["objet", "preavis"]


def test_champs_a_revoir_par_seuils_defaut_personnalise() -> None:
    confiances = {"a": 0.6, "b": 0.6}
    seuils = {"a": 0.5}
    # a : 0.6 >= 0.5 (non retenu) ; b : 0.6 < defaut 0.7 (retenu).
    assert champs_a_revoir_par_seuils(confiances, seuils, defaut=0.7) == ["b"]
