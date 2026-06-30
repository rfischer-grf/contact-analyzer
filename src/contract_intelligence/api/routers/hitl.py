"""Validation humaine (HITL) — gate non négociable (spec §2.4).

- File de revue : champs sous le seuil de confiance d'une extraction (#35).
- Corrections → gold set (#37).
- Signaux valider/rejeter au workflow Temporal en attente (#36) : VALIDE→COMMITE /
  REJETE_METIER côté saga. L'émetteur de signal est une dépendance INJECTABLE
  (import `temporalio` différé dans le corps) ; les tests fournissent un double.

Garde-fou : aucune donnée `à_valider` n'entre dans alertes / ICS / Weaviate. La
décision passe ici, mais la transition d'état effective est portée par la saga.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from ...db import Document, tenant_session
from ...hitl import champs_a_revoir, enregistrer_correction, file_de_revue
from ...hitl.revue import SEUIL_PAR_DEFAUT
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/hitl", tags=["hitl"])

# Émetteur de signal Temporal : (workflow_id, decision) -> None.
SignalSender = Callable[[str, str], Awaitable[None]]


async def _signal_temporal(workflow_id: str, decision: str) -> None:
    """Émet le signal HITL ('valider'/'rejeter') au workflow en attente.

    La saga expose deux signaux nommés distincts (`valider`/`rejeter`) → on
    dispatche selon la décision. Import `temporalio` différé : le routeur ne
    couple pas l'API à `temporalio`.
    """
    from temporalio.client import Client

    from ...config import get_settings
    from ...worker.workflows import IngestionWorkflow

    signaux = {
        "valider": IngestionWorkflow.valider,
        "rejeter": IngestionWorkflow.rejeter,
    }
    signal = signaux[decision]

    settings = get_settings()
    client = await Client.connect(settings.temporal_target, namespace=settings.temporal_namespace)
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(signal)


def get_signal_sender() -> SignalSender:
    return _signal_temporal


class ContratARevoir(BaseModel):
    """Item de la file de revue globale : un contrat `A_VALIDER` en attente (#35)."""

    id: str
    reference: str | None = None
    objet: str | None = None
    date_echeance: date | None = None
    fournisseur_siren: str | None = None


@router.get("/file")
def file_de_revue_endpoint(
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> list[ContratARevoir]:
    """File de revue HITL globale : contrats `A_VALIDER` du tenant (#35).

    Garde-fou §2.4 : seuls les contrats en attente du gate sont listés ; aucun
    contrat `COMMITE`/rejeté n'y figure. Le tenant provient du token (§7).
    """
    with tenant_session(factory, principal.tenant) as session:
        resumes = file_de_revue(session, principal.tenant)
    return [
        ContratARevoir(
            id=resume.id,
            reference=resume.reference,
            objet=resume.objet,
            date_echeance=resume.date_echeance,
            fournisseur_siren=resume.fournisseur_siren,
        )
        for resume in resumes
    ]


class CorrectionEntree(BaseModel):
    """Une correction saisie au gate HITL (ancienne → nouvelle valeur)."""

    champ: str
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None


class CorrectionsRequete(BaseModel):
    corrections: list[CorrectionEntree] = Field(default_factory=list)


@router.post("/contrats/{contrat_id}/corrections", status_code=status.HTTP_201_CREATED)
def enregistrer_corrections(
    contrat_id: str,
    requete: CorrectionsRequete = Body(...),
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, int]:
    """Persiste les corrections pour le tenant du principal (gold set, #37)."""
    with tenant_session(factory, principal.tenant) as session:
        for entree in requete.corrections:
            enregistrer_correction(
                session,
                tenant=principal.tenant,
                contrat_id=contrat_id,
                champ=entree.champ,
                ancienne_valeur=entree.ancienne_valeur,
                nouvelle_valeur=entree.nouvelle_valeur,
                acteur=principal.sujet,
            )
    return {"enregistrees": len(requete.corrections)}


async def _emettre_decision(contrat_id: str, decision: str, sender: SignalSender) -> dict[str, str]:
    try:
        await sender(contrat_id, decision)
    except Exception as exc:  # noqa: BLE001 - remonté en 404 explicite
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Workflow inconnu ou injoignable"
        ) from exc
    return {"statut": "signal_emis", "decision": decision}


@router.post("/contrats/{contrat_id}/valider")
async def valider(
    contrat_id: str,
    principal: Principal = Depends(get_principal),
    sender: SignalSender = Depends(get_signal_sender),
) -> dict[str, str]:
    """Émet le signal `valider` au workflow en attente → VALIDE→COMMITE (#36)."""
    return await _emettre_decision(contrat_id, "valider", sender)


@router.post("/contrats/{contrat_id}/rejeter")
async def rejeter(
    contrat_id: str,
    principal: Principal = Depends(get_principal),
    sender: SignalSender = Depends(get_signal_sender),
) -> dict[str, str]:
    """Émet le signal `rejeter` au workflow en attente → REJETE_METIER (#36)."""
    return await _emettre_decision(contrat_id, "rejeter", sender)


def _confiances_extraction(extraction: dict[str, Any]) -> dict[str, float]:
    """Aplatit l'extraction (`domain.Contrat` sérialisé) en {chemin: confiance}.

    Un `Champ` sérialisé est un dict portant une clé `confiance` (float). On
    descend récursivement les dicts/listes et on retient chaque nœud `Champ`,
    indexé par son chemin pointé (ex. `preavis.delai`, `signataires.0.nom`).
    """
    confiances: dict[str, float] = {}

    def _descendre(noeud: Any, chemin: str) -> None:
        if isinstance(noeud, dict):
            valeur_confiance = noeud.get("confiance")
            if isinstance(valeur_confiance, int | float) and not isinstance(valeur_confiance, bool):
                confiances[chemin] = float(valeur_confiance)
                return  # nœud Champ : pas de descente sous valeur/source
            for cle, sous in noeud.items():
                _descendre(sous, f"{chemin}.{cle}" if chemin else str(cle))
        elif isinstance(noeud, list):
            for i, sous in enumerate(noeud):
                _descendre(sous, f"{chemin}.{i}" if chemin else str(i))

    _descendre(extraction, "")
    return confiances


@router.get("/contrats/{contrat_id}/champs-a-revoir")
def champs_a_revoir_contrat(
    contrat_id: uuid.UUID,
    seuil: float = SEUIL_PAR_DEFAUT,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, list[str]]:
    """Champs de l'extraction du contrat sous le seuil de confiance (#35).

    Lit l'`extraction` du document du contrat. Sans extraction → liste vide.
    """
    with tenant_session(factory, principal.tenant) as session:
        document = (
            session.query(Document)
            .filter(Document.contrat_id == contrat_id, Document.tenant == principal.tenant)
            .order_by(Document.date_signature)
            .first()
        )
        extraction = document.extraction if document is not None else None
    if not extraction:
        return {"champs": []}
    return {"champs": champs_a_revoir(_confiances_extraction(extraction), seuil)}
