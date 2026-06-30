"""Tests des contrôles d'ingestion MIME/taille (#17, spec §2.1)."""

from __future__ import annotations

import pytest

from contract_intelligence.ingestion import ControleRejete, valider_mime, valider_taille


def test_mime_autorise_par_defaut():
    # PDF figure dans get_settings().upload_types_mime → ne lève pas.
    valider_mime("application/pdf")


def test_mime_autorise_avec_parametres_et_casse():
    # Le Content-Type peut porter des paramètres et une casse variable.
    valider_mime("APPLICATION/PDF; charset=binary")


def test_mime_autorise_liste_explicite():
    valider_mime("image/png", autorises=["image/png", "image/jpeg"])


def test_mime_refuse_leve_controle_rejete():
    with pytest.raises(ControleRejete):
        valider_mime("application/x-msdownload")


def test_mime_refuse_hors_liste_explicite():
    with pytest.raises(ControleRejete):
        valider_mime("application/pdf", autorises=["image/png"])


def test_taille_ok_sous_maximum():
    valider_taille(1_000, maximum=2_000)


def test_taille_ok_par_defaut():
    # Bien en dessous du plafond par défaut (50 Mo).
    valider_taille(1_234_567)


def test_taille_egale_au_maximum_acceptee():
    valider_taille(2_000, maximum=2_000)


def test_taille_depassee_leve_controle_rejete():
    with pytest.raises(ControleRejete):
        valider_taille(2_001, maximum=2_000)


@pytest.mark.parametrize("taille", [0, -1])
def test_taille_invalide_leve_controle_rejete(taille: int):
    with pytest.raises(ControleRejete):
        valider_taille(taille, maximum=2_000)
