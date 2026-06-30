"""Corrections HITL → gold set (#37, spec §2.4).

« Les corrections alimentent un gold set. » Chaque correction de champ saisie au
gate HITL est persistée par tenant (vérité terrain), puis exploitable pour mesurer
et améliorer la qualité d'extraction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Correction


def enregistrer_correction(
    session: Session,
    tenant: str,
    contrat_id: uuid.UUID | str,
    champ: str,
    ancienne_valeur: str | None,
    nouvelle_valeur: str | None,
    acteur: str | None,
) -> Correction:
    """Persiste une correction de champ pour le tenant et la renvoie.

    `contrat_id` est normalisé en chaîne (la colonne stocke l'identifiant sous
    forme textuelle, tolérant un UUID ou une référence libre). Le flush rend
    disponibles les valeurs serveur (id, horodatage) sans clore la transaction.
    """
    correction = Correction(
        tenant=tenant,
        contrat_id=str(contrat_id),
        champ=champ,
        ancienne_valeur=ancienne_valeur,
        nouvelle_valeur=nouvelle_valeur,
        acteur=acteur,
    )
    session.add(correction)
    session.flush()
    return correction


def gold_set(session: Session, tenant: str) -> list[Correction]:
    """Renvoie toutes les corrections du tenant, des plus anciennes aux plus récentes.

    NB : l'isolation inter-tenant repose en production sur la RLS PostgreSQL ; le
    filtre `tenant` explicite ici garantit le même périmètre hors RLS (tests SQLite).
    """
    stmt = (
        select(Correction)
        .where(Correction.tenant == tenant)
        .order_by(Correction.horodatage, Correction.id)
    )
    return list(session.execute(stmt).scalars().all())
