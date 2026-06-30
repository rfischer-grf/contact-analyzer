"""Tests de l'extracteur LLM réel (#28, #29, #30, spec §2.3).

Vérifie, **sans dépendance réseau** :
- import différé : `ExtracteurLLM` est importable et instanciable même sans
  `pydantic_ai` installé, et reste conforme au `Protocol` `Extracteur` ;
- `retrieve_clauses_utiles` (helper pur #30) : sur un markdown long multi-sections,
  retient les sections utiles et écarte le bruit ;
- stratégie #30 : markdown complet sous le seuil, retrieve au-delà ;
- mapping #28 : un dict structuré simulé (réponse LLM mockée) se valide en
  `Contrat` Pydantic ;
- le vrai chemin réseau est soit mocké (sans I/O), soit skippé si la lib manque.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import patch

import pytest

from contract_intelligence.config import Settings
from contract_intelligence.domain import Champ, Contrat, Provenance
from contract_intelligence.extraction import (
    Extracteur,
    ExtracteurLLM,
    retrieve_clauses_utiles,
)
from contract_intelligence.extraction.llm import (
    PROMPT_SYSTEME,
    _preparer_entree,
)

# Markdown long, multi-sections : sections utiles + sections « bruit ».
MARKDOWN_LONG = """\
# Préambule
Le présent document est conclu entre les parties désignées ci-après.

## Article 1 - Parties
Le fournisseur ACME Services SAS, SIREN 552 100 554, et le client Groupe RF SA.

## Article 2 - Objet
Prestations de maintenance applicative.

## Annexe technique
Spécifications détaillées des serveurs, ports réseau et schémas d'architecture.

## Article 3 - Durée et reconduction
Durée initiale de trente-six (36) mois, renouvelable par tacite reconduction.

## Article 4 - Résiliation et préavis
Dénonciation moyennant un préavis de trois (3) mois avant l'échéance.

## Conditions générales d'utilisation du portail
Charte graphique, mentions légales et politique de cookies du portail extranet.

## Article 5 - Indexation
Prix révisé selon l'indice Syntec, à la hausse comme à la baisse.

## Article 6 - Montant
Montant annuel de 120 000 € HT.
"""


# --- Import différé + conformité Protocol (#29) -------------------------------


def test_extracteur_llm_importable_sans_pydantic_ai() -> None:
    """Le module extraction s'importe sans `pydantic_ai` (import différé)."""
    import sys

    # `pydantic_ai` n'est pas installé dans l'environnement de test : son absence
    # ne doit empêcher ni l'import du module ni l'instanciation de l'extracteur.
    assert "pydantic_ai" not in sys.modules
    module = importlib.import_module("contract_intelligence.extraction.llm")
    assert hasattr(module, "ExtracteurLLM")
    # Toujours absent après l'import du module (rien n'a été importé au chargement).
    assert "pydantic_ai" not in sys.modules


def test_extracteur_llm_instanciable_sans_reseau() -> None:
    """Instanciation sans réseau ni dépendance LLM (settings injectés)."""
    extracteur = ExtracteurLLM(settings=Settings(llm_base_url="http://exemple.test/v1"))
    assert isinstance(extracteur, ExtracteurLLM)


def test_extracteur_llm_conforme_au_protocol() -> None:
    """`ExtracteurLLM` satisfait le `Protocol` `Extracteur` (runtime_checkable)."""
    extracteur = ExtracteurLLM(settings=Settings())
    assert isinstance(extracteur, Extracteur)


def test_prompt_systeme_cadre_les_consignes() -> None:
    """Le prompt système (français) porte les consignes clés du §3."""
    for attendu in ("confiance", "provenance", "SIREN", "tacite reconduction"):
        assert attendu in PROMPT_SYSTEME


# --- Helper pur retrieve_clauses_utiles (#30) ---------------------------------


def test_retrieve_clauses_utiles_retient_les_sections_utiles() -> None:
    """Sur un markdown long, on garde parties/durée/résiliation/indexation/montant."""
    extrait = retrieve_clauses_utiles(MARKDOWN_LONG)
    for utile in (
        "Parties",
        "Durée et reconduction",
        "Résiliation et préavis",
        "Indexation",
        "Montant",
    ):
        assert utile in extrait


def test_retrieve_clauses_utiles_ecarte_le_bruit() -> None:
    """Les sections non pertinentes (annexe technique, CGU) sont écartées."""
    extrait = retrieve_clauses_utiles(MARKDOWN_LONG)
    assert "Annexe technique" not in extrait
    assert "Conditions générales d'utilisation" not in extrait
    # Le retrieve raccourcit effectivement l'entrée.
    assert len(extrait) < len(MARKDOWN_LONG)


def test_retrieve_clauses_utiles_repli_si_rien_de_pertinent() -> None:
    """Document atypique sans section utile → repli sur le markdown complet."""
    quelconque = "# Notes\nParagraphe sans aucun mot-clé contractuel pertinent."
    assert retrieve_clauses_utiles(quelconque) == quelconque.strip()


def test_retrieve_clauses_utiles_match_corps_sans_titre_utile() -> None:
    """Une section au titre neutre mais au corps porteur de mot-clé est gardée."""
    markdown = (
        "# Section A\nCe paragraphe mentionne un préavis de trois mois.\n"
        "# Section B\nTexte totalement hors sujet."
    )
    extrait = retrieve_clauses_utiles(markdown)
    assert "préavis" in extrait
    assert "hors sujet" not in extrait


def test_retrieve_clauses_utiles_est_deterministe() -> None:
    """Helper pur : même entrée → même sortie."""
    assert retrieve_clauses_utiles(MARKDOWN_LONG) == retrieve_clauses_utiles(MARKDOWN_LONG)


# --- Stratégie d'entrée markdown complet vs retrieve (#30) --------------------


def test_preparer_entree_markdown_complet_sous_le_seuil() -> None:
    """Sous le seuil : on transmet le markdown complet, inchangé."""
    assert _preparer_entree(MARKDOWN_LONG, seuil_caracteres=10_000) == MARKDOWN_LONG


def test_preparer_entree_retrieve_au_dela_du_seuil() -> None:
    """Au-delà du seuil : on bascule sur le retrieve des clauses utiles."""
    entree = _preparer_entree(MARKDOWN_LONG, seuil_caracteres=10)
    assert entree == retrieve_clauses_utiles(MARKDOWN_LONG)
    assert "Annexe technique" not in entree


def test_preparer_entree_seuil_limite_inclusif() -> None:
    """Longueur == seuil → markdown complet (≤ seuil, pas de retrieve)."""
    texte = "abcdef"
    assert _preparer_entree(texte, seuil_caracteres=len(texte)) == texte


# --- Mapping sortie structurée → Contrat Pydantic (#28), sans réseau ----------


def _reponse_llm_simulee() -> dict[str, Any]:
    """Réponse LLM structurée simulée (forme attendue par `Contrat`, §3)."""
    return {
        "fournisseur": {
            "raison_sociale": {
                "valeur": "ACME Services SAS",
                "confiance": 0.96,
                "source": {"page": 1, "extrait": "ACME Services SAS"},
            },
            "siren": {
                "valeur": "552100554",
                "confiance": 0.94,
                "source": {"page": 1, "extrait": "SIREN 552 100 554"},
            },
        },
        "client": {
            "raison_sociale": {
                "valeur": "Groupe RF SA",
                "confiance": 0.95,
                "source": {"page": 1, "extrait": "Groupe RF SA"},
            }
        },
        "date_echeance": {
            "valeur": "2026-12-31",
            "confiance": 0.9,
            "source": {"page": 2, "extrait": "jusqu'au 31 décembre 2026"},
        },
        "preavis": {
            "delai": {
                "valeur": 3,
                "confiance": 0.92,
                "source": {"page": 5, "extrait": "préavis de trois (3) mois"},
            },
            "unite": {
                "valeur": "mois",
                "confiance": 0.91,
                "source": {"page": 5, "extrait": "trois mois"},
            },
        },
        "indexation": {
            "indice": {
                "valeur": "syntec",
                "confiance": 0.9,
                "source": {"page": 6, "extrait": "indice Syntec"},
            },
            "bidirectionnelle": {
                "valeur": True,
                "confiance": 0.88,
                "source": {"page": 6, "extrait": "à la hausse comme à la baisse"},
            },
        },
    }


def test_mapping_reponse_structuree_vers_contrat() -> None:
    """Un dict structuré simulé se valide en `Contrat` Pydantic (#28), sans réseau."""
    contrat = Contrat.model_validate(_reponse_llm_simulee())
    assert isinstance(contrat, Contrat)
    # Chaque champ porte valeur + confiance + provenance (invariant §3).
    assert isinstance(contrat.fournisseur.raison_sociale, Champ)
    assert contrat.fournisseur.raison_sociale.valeur == "ACME Services SAS"
    assert isinstance(contrat.fournisseur.raison_sociale.source, Provenance)
    assert contrat.preavis is not None
    assert contrat.preavis.delai.valeur == 3
    assert contrat.indexation is not None
    assert contrat.indexation.indice.valeur.value == "syntec"
    assert contrat.date_echeance is not None
    assert contrat.date_echeance.valeur.isoformat() == "2026-12-31"


def test_mapping_confiance_hors_bornes_rejetee() -> None:
    """La re-validation Pydantic rejette une confiance hors [0, 1] (#28)."""
    mauvais = _reponse_llm_simulee()
    mauvais["fournisseur"]["raison_sociale"]["confiance"] = 1.5
    with pytest.raises(ValueError):
        Contrat.model_validate(mauvais)


# --- Chemin réseau : mocké si possible, skippé sinon --------------------------


def test_extraire_appel_mocke_renvoie_un_contrat() -> None:
    """`extraire` orchestre l'agent et renvoie sa sortie structurée (sans réseau).

    On mocke `_construire_agent` pour éviter toute I/O : l'agent factice renvoie un
    `Contrat` validé. On vérifie aussi que l'entrée transmise applique bien la
    stratégie #30 (ici, retrieve car le seuil est volontairement bas).
    """

    class _ResultatFactice:
        def __init__(self, contrat: Contrat) -> None:
            self.output = contrat

    class _AgentFactice:
        def __init__(self, contrat: Contrat) -> None:
            self._contrat = contrat
            self.entree_recue: str | None = None

        def run_sync(self, entree: str) -> _ResultatFactice:
            self.entree_recue = entree
            return _ResultatFactice(self._contrat)

    contrat_attendu = Contrat.model_validate(_reponse_llm_simulee())
    agent_factice = _AgentFactice(contrat_attendu)

    extracteur = ExtracteurLLM(
        settings=Settings(
            llm_base_url="http://exemple.test/v1",
            llm_seuil_retrieve_caracteres=10,  # force le retrieve (#30)
        )
    )
    with patch.object(extracteur, "_construire_agent", return_value=agent_factice):
        contrat = extracteur.extraire(MARKDOWN_LONG)

    assert contrat is contrat_attendu
    # Stratégie #30 effectivement appliquée : retrieve, pas markdown complet.
    assert agent_factice.entree_recue == retrieve_clauses_utiles(MARKDOWN_LONG)


def test_construire_agent_exige_base_url() -> None:
    """Sans `llm_base_url`, `extraire` échoue clairement (config requise #29).

    `pytest.importorskip` : ce chemin tente l'import différé de `pydantic_ai` ;
    si la lib n'est pas installée, le test est skippé (on n'exige pas la dépendance
    `extraction` pour la suite). Avec la lib, on vérifie l'erreur de configuration.
    """
    pytest.importorskip("pydantic_ai")
    extracteur = ExtracteurLLM(settings=Settings(llm_base_url=None))
    with pytest.raises(RuntimeError, match="llm_base_url"):
        extracteur.extraire("# Contrat\nContenu minimal.")
