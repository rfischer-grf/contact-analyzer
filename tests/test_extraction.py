"""Tests de la couche extraction (epic #63, #31).

Vérifie que :
- `FakeExtracteur` est un `Extracteur` et produit un `Contrat` dont chaque
  `Champ` porte valeur + confiance + `source` (Provenance), validé Pydantic ;
- `champs_sous_seuil` détecte les champs peu fiables (y compris imbriqués
  `preavis.*` / `indexation.*`), respecte la stricte infériorité, et ignore
  les champs très confiants ;
- les seuils par champ durcissent bien les champs actionnables.
"""

from __future__ import annotations

from contract_intelligence.domain import Champ, Contrat, Partie, Provenance
from contract_intelligence.extraction import (
    SEUIL_GENERIQUE,
    SEUILS_PAR_DEFAUT,
    Extracteur,
    FakeExtracteur,
    champs_sous_seuil,
)
from contract_intelligence.extraction.seuils import _champs_du_contrat


def _partie(raison: str, confiance: float = 0.99) -> Partie:
    return Partie(raison_sociale=Champ[str](valeur=raison, confiance=confiance))


def test_fake_est_un_extracteur() -> None:
    # Conformité au Protocol (runtime_checkable).
    assert isinstance(FakeExtracteur(), Extracteur)


def test_fake_produit_un_contrat_valide() -> None:
    contrat = FakeExtracteur().extraire("# Contrat\n...markdown Docling...")
    assert isinstance(contrat, Contrat)
    # Round-trip Pydantic : la structure est bien un Contrat valide (§3).
    Contrat.model_validate(contrat.model_dump())


def test_chaque_champ_porte_valeur_confiance_source() -> None:
    contrat = FakeExtracteur().extraire("markdown")
    champs = _champs_du_contrat(contrat)
    # Le fake remplit un contrat non trivial.
    assert len(champs) >= 10
    for nom, champ in champs.items():
        assert isinstance(champ, Champ), nom
        assert champ.valeur is not None, nom
        assert 0.0 <= champ.confiance <= 1.0, nom
        assert isinstance(champ.source, Provenance), nom
        assert champ.source.extrait, nom


def test_champs_sous_seuil_detecte_les_champs_du_fake() -> None:
    contrat = FakeExtracteur().extraire("markdown")
    sous_seuil = champs_sous_seuil(contrat)
    # Champs volontairement peu fiables dans le fake.
    assert "client.siren" in sous_seuil  # 0.55 < 0.8 (générique)
    assert "date_echeance" in sous_seuil  # 0.6 < 0.9 (actionnable strict)
    assert "preavis.unite" in sous_seuil  # 0.7 < 0.9 (actionnable strict)
    # Champ très confiant : jamais en revue.
    assert "devise" not in sous_seuil  # 0.99
    assert "fournisseur.raison_sociale" not in sous_seuil  # 0.97


def test_champs_sous_seuil_seuil_global_float() -> None:
    contrat = FakeExtracteur().extraire("markdown")
    # Seuil global laxiste : seuls les très faibles ressortent.
    laxiste = champs_sous_seuil(contrat, seuils=0.6)
    assert laxiste == ["client.siren"]  # seul 0.55 < 0.6
    # Seuil global sévère : presque tout ressort.
    severe = champs_sous_seuil(contrat, seuils=1.0)
    assert "devise" in severe and "client.siren" in severe


def test_champs_sous_seuil_stricte_inferiorite() -> None:
    # Confiance == seuil → NON retenu (cf. file de revue HITL).
    contrat = Contrat(
        fournisseur=_partie("F", confiance=SEUIL_GENERIQUE),
        client=_partie("C", confiance=SEUIL_GENERIQUE - 0.01),
    )
    sous_seuil = champs_sous_seuil(contrat, seuils=SEUIL_GENERIQUE)
    assert "fournisseur.raison_sociale" not in sous_seuil  # == seuil
    assert "client.raison_sociale" in sous_seuil  # < seuil


def test_champ_tres_confiant_jamais_liste() -> None:
    contrat = Contrat(
        fournisseur=_partie("F", confiance=1.0),
        client=_partie("C", confiance=1.0),
    )
    assert champs_sous_seuil(contrat) == []
    assert champs_sous_seuil(contrat, seuils=0.99) == []


def test_seuils_par_defaut_durcit_les_champs_actionnables() -> None:
    # Les champs actionnables sont strictement au-dessus du seuil générique.
    for nom in ("date_echeance", "preavis.delai", "indexation.indice"):
        assert SEUILS_PAR_DEFAUT[nom] > SEUIL_GENERIQUE
