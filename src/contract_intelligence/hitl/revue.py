"""File de revue HITL — champs sous le seuil de confiance + file globale (#35, spec §2.4).

Deux niveaux de revue :

- Par champ : les champs dont la confiance passe sous un seuil tombent dans la file
  de revue ; l'UI affiche le champ + le surlignage de la source pour correction.
- Globale : la liste des contrats `A_VALIDER` du tenant en attente au gate HITL,
  qu'un relecteur prend en charge un par un (`file_de_revue`).

Ce module porte la logique pure (sélection des champs, sélection des contrats en
attente) ; la lecture de l'extraction et l'exposition HTTP relèvent du routeur API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Contrat

SEUIL_PAR_DEFAUT = 0.8

# État de la saga d'ingestion en attente du gate HITL (cf. spec §2.4, §4).
ETAT_A_VALIDER = "A_VALIDER"


@dataclass(frozen=True)
class ResumeContratARevoir:
    """Résumé d'un contrat en attente de validation (item de la file de revue globale).

    Ne porte que les champs d'identification/échéance utiles à l'arbitrage de la
    file ; le détail (champs à revoir, extraction) est récupéré contrat par contrat.
    """

    id: str
    reference: str | None
    objet: str | None
    date_echeance: date | None
    fournisseur_siren: str | None


def file_de_revue(session: Session, tenant: str) -> list[ResumeContratARevoir]:
    """Renvoie les contrats `A_VALIDER` du tenant en attente au gate HITL (#35).

    Sélection `WHERE tenant = … AND etat == 'A_VALIDER'`, ordonnée par échéance
    croissante (les plus urgentes d'abord ; échéances nulles en queue). L'isolation
    inter-tenant repose en production sur la RLS PostgreSQL ; le filtre `tenant`
    explicite garantit le même périmètre hors RLS (tests SQLite).
    """
    stmt = (
        select(Contrat)
        .where(Contrat.tenant == tenant, Contrat.etat == ETAT_A_VALIDER)
        .order_by(Contrat.date_echeance.is_(None), Contrat.date_echeance, Contrat.id)
    )
    contrats = session.execute(stmt).scalars().all()
    return [
        ResumeContratARevoir(
            id=str(contrat.id),
            reference=contrat.reference,
            objet=contrat.objet,
            date_echeance=contrat.date_echeance,
            fournisseur_siren=contrat.fournisseur_siren,
        )
        for contrat in contrats
    ]


def champs_a_revoir(
    champs_confiance: dict[str, float], seuil: float = SEUIL_PAR_DEFAUT
) -> list[str]:
    """Renvoie, triés, les noms des champs dont la confiance est < `seuil`.

    `champs_confiance` mappe nom de champ → score de confiance ∈ [0, 1]
    (cf. wrapper `Champ`). Un champ dont la confiance vaut exactement le seuil
    est considéré comme suffisamment fiable et n'est PAS retenu.

    La file de revue GLOBALE (contrats `A_VALIDER` du tenant) est portée par
    `file_de_revue` ; ici on ne traite que les champs d'une extraction.
    """
    return sorted(nom for nom, confiance in champs_confiance.items() if confiance < seuil)


def champs_a_revoir_par_seuils(
    champs_confiance: dict[str, float],
    seuils: dict[str, float],
    defaut: float = SEUIL_PAR_DEFAUT,
) -> list[str]:
    """Variante avec seuil par champ : `seuils[nom]`, sinon `defaut`.

    Permet d'exiger une confiance plus élevée sur les champs critiques (préavis,
    date d'échéance) qu'on ne tolère pas mal extraits, sans durcir le seuil global.
    """
    return sorted(
        nom for nom, confiance in champs_confiance.items() if confiance < seuils.get(nom, defaut)
    )
