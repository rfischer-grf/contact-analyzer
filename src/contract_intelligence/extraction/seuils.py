"""Seuils de confiance et file de revue HITL (#31, spec §2.4).

Chaque champ extrait porte une confiance ∈ [0, 1] (wrapper `Champ`). Sous le
seuil, le champ tombe dans la **file de revue** : aucune donnée `à_valider` ne
doit polluer alertes / ICS / Weaviate (gate HITL non négociable). On durcit le
seuil sur les champs actionnables (dates, préavis) car « un préavis ou une date
mal extraits = engagement raté » (§2.4).

Logique pure : on parcourt les `Champ` du `Contrat` (y compris ceux imbriqués
dans `preavis` et `indexation`) et on renvoie les noms de ceux à revoir. La
lecture de l'extraction et l'exposition HTTP relèvent du routeur API / de la
saga ; ici on ne traite que les champs d'une extraction.
"""

from __future__ import annotations

from contract_intelligence.domain import Champ, Contrat

# Seuil générique : en deçà, le champ part en revue.
SEUIL_GENERIQUE = 0.8

# Seuils par champ. Les champs actionnables (dates d'effet/échéance, préavis,
# durées qui décalent l'échéance) sont stricts à 0.9 : une erreur y rate un
# engagement. Les noms de clés correspondent aux noms renvoyés par
# `champs_sous_seuil` (champs imbriqués préfixés `preavis.` / `indexation.`).
SEUILS_PAR_DEFAUT: dict[str, float] = {
    "date_effet": 0.9,
    "date_echeance": 0.9,
    "duree_initiale_mois": 0.9,
    "tacite_reconduction": 0.9,
    "duree_reconduction_mois": 0.9,
    "preavis.delai": 0.9,
    "preavis.unite": 0.9,
    "indexation.indice": 0.9,
    "indexation.indice_base_valeur": 0.9,
}


def _seuil_pour(nom: str, seuils: dict[str, float] | float) -> float:
    """Seuil applicable à `nom` : valeur scalaire globale, ou table par champ."""
    if isinstance(seuils, dict):
        return seuils.get(nom, SEUIL_GENERIQUE)
    return seuils


def _champs_du_contrat(contrat: Contrat) -> dict[str, Champ[object]]:
    """Aplatit les `Champ` du contrat en `nom_qualifié -> Champ`.

    Inclut les champs imbriqués des sous-modèles `Partie` (fournisseur/client),
    `Preavis` et `ClauseIndexation`, préfixés par leur conteneur pour rester
    désambiguïsables (ex. `preavis.delai`, `indexation.indice`).
    """
    champs: dict[str, Champ[object]] = {}

    def _ajouter(prefixe: str, modele: object) -> None:
        # Parcourt les attributs d'un BaseModel et retient ceux qui sont des Champ.
        for nom, valeur in vars(modele).items():
            if isinstance(valeur, Champ):
                champs[f"{prefixe}{nom}"] = valeur

    _ajouter("fournisseur.", contrat.fournisseur)
    _ajouter("client.", contrat.client)
    for i, signataire in enumerate(contrat.signataires):
        _ajouter(f"signataires[{i}].", signataire)
    _ajouter("", contrat)
    if contrat.preavis is not None:
        _ajouter("preavis.", contrat.preavis)
    if contrat.indexation is not None:
        _ajouter("indexation.", contrat.indexation)

    return champs


def champs_sous_seuil(
    contrat: Contrat,
    seuils: dict[str, float] | float = SEUILS_PAR_DEFAUT,
) -> list[str]:
    """Renvoie, triés, les noms des champs du `contrat` à envoyer en revue (#31).

    Parcourt tous les `Champ` du contrat — y compris ceux imbriqués dans
    `preavis` et `indexation` — et retient ceux dont `confiance` est
    **strictement** inférieure au seuil applicable. Un champ dont la confiance
    vaut exactement le seuil est jugé suffisamment fiable et n'est PAS retenu.

    `seuils` : table `nom_qualifié -> seuil` (défaut `SEUILS_PAR_DEFAUT`, qui
    durcit les champs actionnables à 0.9, le reste à `SEUIL_GENERIQUE`), ou un
    `float` unique appliqué uniformément à tous les champs.
    """
    return sorted(
        nom
        for nom, champ in _champs_du_contrat(contrat).items()
        if champ.confiance < _seuil_pour(nom, seuils)
    )
