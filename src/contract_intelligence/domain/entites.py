"""Entités extraites (cf. spec §3).

`document` (pièce physique) ≠ `contrat` (entité logique = état effectif folé sur
la chaîne de documents). Ce module modélise les champs extraits d'une pièce ;
l'état effectif et la persistance relèvent de la couche données (tickets #8–#13).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from .champ import Champ


class Indice(StrEnum):
    syntec = "syntec"
    ilat = "ilat"
    ilc = "ilc"
    icc = "icc"
    insee_autre = "insee_autre"
    aucun = "aucun"


class UnitePreavis(StrEnum):
    jours = "jours"
    mois = "mois"


class Partie(BaseModel):
    raison_sociale: Champ[str]
    siren: Champ[str] | None = None
    forme_juridique: Champ[str] | None = None
    adresse: Champ[str] | None = None


class Signataire(BaseModel):
    nom: Champ[str]
    qualite: Champ[str] | None = None
    pour_le_compte_de: Champ[str] | None = None
    date_signature: Champ[date] | None = None


class ClauseIndexation(BaseModel):
    indice: Champ[Indice]
    indice_base_valeur: Champ[float] | None = None  # S0
    indice_base_periode: Champ[str] | None = None
    formule: Champ[str] | None = None
    part_fixe: Champ[float] | None = None
    periodicite: Champ[str] | None = None
    bidirectionnelle: Champ[bool] | None = None


class Preavis(BaseModel):
    delai: Champ[int]
    unite: Champ[UnitePreavis]
    modalites: Champ[str] | None = None


class Contrat(BaseModel):
    """Champs extraits d'une pièce. NB : `date_limite_denonciation` n'est PAS un
    champ — elle est calculée en aval (échéance − préavis), cf. `domain.calculs`.
    """

    fournisseur: Partie
    client: Partie
    signataires: list[Signataire] = Field(default_factory=list)
    objet: Champ[str] | None = None
    date_effet: Champ[date] | None = None
    date_echeance: Champ[date] | None = None
    duree_initiale_mois: Champ[int] | None = None
    tacite_reconduction: Champ[bool] | None = None
    duree_reconduction_mois: Champ[int] | None = None
    preavis: Preavis | None = None
    indexation: ClauseIndexation | None = None
    montant: Champ[float] | None = None
    devise: Champ[str] | None = None
