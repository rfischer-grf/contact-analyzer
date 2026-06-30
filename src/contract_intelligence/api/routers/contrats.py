"""Lecture des contrats + projection tarifaire pour le front Clausio (#84, #87).

Lecture seule sur l'**état effectif** (table `contrat`, alimentée après COMMITE).
Le `tenant` provient du token (principal), jamais du client (§7) ; les requêtes
passent par `tenant_session` (RLS).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ...db import Contrat, tenant_session
from ...indexation import projeter_tarif
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/contrats", tags=["contrats"])


def _resume(c: Contrat) -> dict[str, object]:
    return {
        "id": str(c.id),
        "reference": c.reference,
        "objet": c.objet,
        "fournisseur_siren": c.fournisseur_siren,
        "indice": c.indice,
        "montant": float(c.montant) if c.montant is not None else None,
        "devise": c.devise,
        "date_echeance": c.date_echeance.isoformat() if c.date_echeance else None,
        "date_limite_denonciation": (
            c.date_limite_denonciation.isoformat() if c.date_limite_denonciation else None
        ),
    }


@router.get("")
def lister(
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
    indice: str | None = Query(default=None),
    fournisseur_siren: str | None = Query(default=None),
    echeance_avant: date | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    """Liste paginée/filtrée des contrats du tenant (facettes structurées)."""
    with tenant_session(factory, principal.tenant) as session:
        stmt = select(Contrat).where(Contrat.tenant == principal.tenant)
        if indice is not None:
            stmt = stmt.where(Contrat.indice == indice)
        if fournisseur_siren is not None:
            stmt = stmt.where(Contrat.fournisseur_siren == fournisseur_siren)
        if echeance_avant is not None:
            stmt = stmt.where(Contrat.date_echeance <= echeance_avant)
        stmt = stmt.order_by(Contrat.date_echeance).limit(limite).offset(decalage)
        return [_resume(c) for c in session.execute(stmt).scalars().all()]


@router.get("/{contrat_id}")
def detail(
    contrat_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, object]:
    """Détail d'un contrat : état effectif + chaîne ordonnée des documents."""
    with tenant_session(factory, principal.tenant) as session:
        c = session.get(Contrat, contrat_id)
        if c is None or c.tenant != principal.tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contrat introuvable")
        documents = [
            {
                "sha256": d.sha256,
                "numero_avenant": d.numero_avenant,
                "reference": d.reference,
                "date_signature": d.date_signature.isoformat(),
            }
            for d in c.documents
        ]
        return {
            **_resume(c),
            "duree_initiale_mois": c.duree_initiale_mois,
            "tacite_reconduction": c.tacite_reconduction,
            "preavis_delai": c.preavis_delai,
            "preavis_unite": c.preavis_unite,
            "indice_base_valeur": (
                float(c.indice_base_valeur) if c.indice_base_valeur is not None else None
            ),
            "indice_base_periode": c.indice_base_periode,
            "date_acte_reference": (
                c.date_acte_reference.isoformat() if c.date_acte_reference else None
            ),
            "bidirectionnelle": c.bidirectionnelle,
            "documents": documents,
        }


class ProjectionRequete(BaseModel):
    date_revision: date
    part_fixe: float | None = Field(default=None, ge=0, le=1)


@router.post("/{contrat_id}/projection")
def projection(
    contrat_id: uuid.UUID,
    requete: ProjectionRequete,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, object]:
    """Projette le tarif révisé `P1` à une date donnée (moteur §2.5)."""
    with tenant_session(factory, principal.tenant) as session:
        c = session.get(Contrat, contrat_id)
        if c is None or c.tenant != principal.tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contrat introuvable")
        try:
            res = projeter_tarif(session, c, requete.date_revision, requete.part_fixe)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return {
            "p0": res.p0,
            "s0": res.s0,
            "s1": res.s1,
            "coefficient_raccord": res.coefficient_raccord,
            "p1": res.p1,
            "periode_s0": res.periode_s0,
            "periode_s1": res.periode_s1,
        }
