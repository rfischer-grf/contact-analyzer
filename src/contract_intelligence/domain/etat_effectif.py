"""État effectif d'un contrat = fold sur la chaîne de documents (spec §3.1).

`contrat` (entité logique) ne stocke pas des champs bruts mais **l'état effectif
calculé** : on rejoue les pièces dans l'ordre de signature et on applique chaque
avenant (durée→échéance, préavis→date limite, indice/base, montant).

Garde-fous (§7) appliqués ici :
- clause d'indexation **unidirectionnelle** (hausse seule) = réputée non écrite →
  on **force le bidirectionnel** ;
- `date_limite_denonciation` est **calculée** (échéance − préavis), jamais extraite ;
- re-ancrage tarifaire : un avenant de prix re-fixe `montant`/`S0` et la
  `date_acte_reference` à sa propre date de signature.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel

from .calculs import calculer_date_limite_denonciation
from .champ import Champ
from .entites import Contrat, Indice, UnitePreavis


def _val(champ: Champ[Any] | None) -> Any:
    """Valeur d'un champ extrait, ou None s'il est absent / vide."""
    return champ.valeur if champ is not None else None


class EtatEffectif(BaseModel):
    """État effectif calculé, exploité par les alertes, l'ICS et la projection RAG."""

    fournisseur_siren: str | None = None
    client_siren: str | None = None
    objet: str | None = None
    date_effet: date | None = None
    date_echeance: date | None = None
    duree_initiale_mois: int | None = None
    tacite_reconduction: bool | None = None
    preavis_delai: int | None = None
    preavis_unite: UnitePreavis | None = None
    indice: Indice | None = None
    indice_base_valeur: float | None = None  # S0
    indice_base_periode: str | None = None
    date_acte_reference: date | None = None  # signature du dernier acte tarifaire
    montant: float | None = None
    devise: str | None = None
    # §7 : la révision est toujours bidirectionnelle dans le moteur.
    bidirectionnelle: bool = True
    # Dérivée (échéance − préavis), jamais extraite.
    date_limite_denonciation: date | None = None


@dataclass(frozen=True)
class PieceVersee:
    """Une pièce physique de la chaîne (contrat d'origine ou avenant)."""

    date_signature: date
    contrat: Contrat
    numero_avenant: int | None = None


def _appliquer(etat: EtatEffectif, piece: PieceVersee) -> None:
    """Applique (override des champs renseignés) une pièce à l'état courant."""
    c = piece.contrat

    # Identité des parties : on projette le SIREN (clé de rapprochement, §3.1).
    if (siren := _val(c.fournisseur.siren)) is not None:
        etat.fournisseur_siren = siren
    if (siren := _val(c.client.siren)) is not None:
        etat.client_siren = siren

    for attr, champ in (
        ("objet", c.objet),
        ("date_effet", c.date_effet),
        ("date_echeance", c.date_echeance),
        ("duree_initiale_mois", c.duree_initiale_mois),
        ("tacite_reconduction", c.tacite_reconduction),
        ("devise", c.devise),
    ):
        if (v := _val(champ)) is not None:
            setattr(etat, attr, v)

    if c.preavis is not None:
        if (delai := _val(c.preavis.delai)) is not None:
            etat.preavis_delai = delai
        if (unite := _val(c.preavis.unite)) is not None:
            etat.preavis_unite = unite

    if c.indexation is not None and (indice := _val(c.indexation.indice)) is not None:
        etat.indice = indice
        if (s0 := _val(c.indexation.indice_base_valeur)) is not None:
            etat.indice_base_valeur = s0
        if (periode := _val(c.indexation.indice_base_periode)) is not None:
            etat.indice_base_periode = periode
        # §7 : clause hausse-seule réputée non écrite → bidirectionnel forcé.
        etat.bidirectionnelle = True
        # Re-ancrage tarifaire à la date de l'acte (#34).
        etat.date_acte_reference = piece.date_signature

    if (montant := _val(c.montant)) is not None:
        etat.montant = montant
        # Un avenant de prix re-fixe l'acte de référence tarifaire (#34).
        etat.date_acte_reference = piece.date_signature


def fold_etat_effectif(pieces: Iterable[PieceVersee]) -> EtatEffectif:
    """Rejoue la chaîne de documents (ordre de signature) → état effectif.

    Recalcule en fin de fold la `date_limite_denonciation` (échéance − préavis).
    """
    etat = EtatEffectif()
    for piece in sorted(pieces, key=lambda p: p.date_signature):
        _appliquer(etat, piece)

    if (
        etat.date_echeance is not None
        and etat.preavis_delai is not None
        and etat.preavis_unite is not None
    ):
        etat.date_limite_denonciation = calculer_date_limite_denonciation(
            etat.date_echeance, etat.preavis_delai, etat.preavis_unite
        )
    else:
        etat.date_limite_denonciation = None

    return etat
