"""Rapprochement avenant→parent — matching fuzzy (spec §3.1, tickets #32/#33).

Un avenant est une pièce physique qui modifie un contrat existant (durée, préavis,
indice/base, montant). Pour rejouer la chaîne et réécrire l'état effectif, encore
faut-il savoir **à quel contrat parent** il se rattache. Ce lien est *fuzzy* : il
s'appuie sur le SIREN des parties, la référence et l'objet de la pièce.

Garde-fou §7 — **JAMAIS d'auto-lien.** Ce module ne fait que **proposer** des
candidats classés (étape RAPPROCHEMENT de la saga). La confirmation se fait dans
le gate HITL : rattacher au mauvais parent corromprait silencieusement les
échéances. Aucune fonction ici ne crée ou ne persiste un lien.

Aucune dépendance tierce : la similarité textuelle utilise `difflib` (stdlib).

Pondération (somme = 1,0) :

- SIREN fournisseur identique  → 0,25
- SIREN client identique       → 0,25
  (les deux SIREN sont le signal fort : 0,50 réparti, comparaison exacte après
  normalisation — suppression des espaces.)
- similarité `reference` (`difflib.SequenceMatcher`) → 0,25
- similarité `objet`      (`difflib.SequenceMatcher`) → 0,25
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

#: Poids du SIREN fournisseur identique (signal fort).
POIDS_SIREN_FOURNISSEUR = 0.25
#: Poids du SIREN client identique (signal fort).
POIDS_SIREN_CLIENT = 0.25
#: Poids de la similarité textuelle de la référence.
POIDS_REFERENCE = 0.25
#: Poids de la similarité textuelle de l'objet.
POIDS_OBJET = 0.25


@dataclass(frozen=True)
class PartiesRef:
    """Signature de rapprochement d'une pièce (avenant ou contrat candidat).

    Tous les champs sont optionnels : une extraction LLM peut ne pas avoir capté
    un SIREN ou une référence. Un champ manquant ne contribue simplement pas au
    score (cf. comparaisons ci-dessous).
    """

    siren_fournisseur: str | None = None
    siren_client: str | None = None
    reference: str | None = None
    objet: str | None = None


@dataclass
class Candidat:
    """Candidat parent proposé pour un avenant. `details` ventile le score par
    composante (siren_fournisseur, siren_client, reference, objet) pour l'audit
    et l'affichage HITL.
    """

    contrat_id: str
    score: float
    details: dict[str, float] = field(default_factory=dict)


def _normaliser_siren(siren: str | None) -> str | None:
    """Retire les espaces d'un SIREN ; ``None`` ou chaîne vide → ``None``."""
    if siren is None:
        return None
    nettoye = "".join(siren.split())
    return nettoye or None


def _siren_identique(a: str | None, b: str | None) -> bool:
    """Égalité exacte de deux SIREN après normalisation (espaces retirés).

    Deux SIREN absents ne « matchent » pas : l'absence n'est pas un signal.
    """
    na = _normaliser_siren(a)
    nb = _normaliser_siren(b)
    return na is not None and na == nb


def _similarite_texte(a: str | None, b: str | None) -> float:
    """Similarité dans [0,1] via `difflib.SequenceMatcher`, insensible à la casse
    et aux espaces de bord. Renvoie 0,0 si l'un des textes manque.
    """
    if a is None or b is None:
        return 0.0
    ga = a.strip().casefold()
    gb = b.strip().casefold()
    if not ga or not gb:
        return 0.0
    return SequenceMatcher(None, ga, gb).ratio()


def score_similarite(avenant: PartiesRef, candidat: PartiesRef) -> float:
    """Score de rapprochement dans [0,1] entre un avenant et un contrat candidat.

    Combine, selon la pondération du module (somme = 1,0) : égalité exacte des
    SIREN fournisseur et client (signal fort, 0,50 réparti) et similarité
    textuelle de la référence et de l'objet (`difflib`).
    """
    return sum(_composantes(avenant, candidat).values())


def _composantes(avenant: PartiesRef, candidat: PartiesRef) -> dict[str, float]:
    """Contribution pondérée de chaque composante (ventilation pour l'audit)."""
    return {
        "siren_fournisseur": (
            POIDS_SIREN_FOURNISSEUR
            if _siren_identique(avenant.siren_fournisseur, candidat.siren_fournisseur)
            else 0.0
        ),
        "siren_client": (
            POIDS_SIREN_CLIENT
            if _siren_identique(avenant.siren_client, candidat.siren_client)
            else 0.0
        ),
        "reference": POIDS_REFERENCE * _similarite_texte(avenant.reference, candidat.reference),
        "objet": POIDS_OBJET * _similarite_texte(avenant.objet, candidat.objet),
    }


def proposer_candidats(
    avenant: PartiesRef,
    candidats: dict[str, PartiesRef],
    seuil: float = 0.5,
) -> list[Candidat]:
    """Propose les contrats parents plausibles pour un avenant, triés par score
    décroissant. `contrat_id` = clé du dict `candidats`. Seuls les candidats dont
    le score est **≥ seuil** sont renvoyés.

    Garde-fou §7 — **JAMAIS d'auto-lien.** Le résultat est une **proposition** pour
    l'étape RAPPROCHEMENT ; le rattachement effectif n'est confirmé qu'en gate HITL.
    Cette fonction ne crée ni ne persiste aucun lien.
    """
    proposes: list[Candidat] = []
    for contrat_id, ref in candidats.items():
        details = _composantes(avenant, ref)
        score = sum(details.values())
        if score >= seuil:
            proposes.append(Candidat(contrat_id=contrat_id, score=score, details=details))
    # Tri par score décroissant ; départage stable par contrat_id pour un ordre
    # déterministe à scores égaux.
    proposes.sort(key=lambda c: (-c.score, c.contrat_id))
    return proposes
