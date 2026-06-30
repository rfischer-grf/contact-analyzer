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

from ...config import Settings, get_settings
from ...db import Document, tenant_session
from ...hitl import enregistrer_correction, file_de_revue
from ...hitl.revue import SEUIL_PAR_DEFAUT
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/hitl", tags=["hitl"])

# Émetteur de signal Temporal : (workflow_id, decision, parent_contrat_id?) -> None.
SignalSender = Callable[[str, str, str | None], Awaitable[None]]


async def _signal_temporal(
    workflow_id: str, decision: str, parent_contrat_id: str | None = None
) -> None:
    """Émet le signal HITL ('valider'/'rejeter') au workflow en attente.

    La saga expose deux signaux nommés distincts (`valider`/`rejeter`) → on
    dispatche selon la décision. À la validation, `parent_contrat_id` (optionnel)
    porte le parent confirmé pour un avenant (#33) ; il est transmis comme argument
    du signal `valider`. Import `temporalio` différé : le routeur ne couple pas
    l'API à `temporalio`.
    """
    from temporalio.client import Client

    from ...config import get_settings
    from ...worker.workflows import IngestionWorkflow

    settings = get_settings()
    client = await Client.connect(settings.temporal_target, namespace=settings.temporal_namespace)
    handle = client.get_workflow_handle(workflow_id)
    if decision == "valider":
        await handle.signal(IngestionWorkflow.valider, parent_contrat_id)
    else:
        await handle.signal(IngestionWorkflow.rejeter)


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


async def _emettre_decision(
    contrat_id: str,
    decision: str,
    sender: SignalSender,
    parent_contrat_id: str | None = None,
) -> dict[str, str]:
    try:
        await sender(contrat_id, decision, parent_contrat_id)
    except Exception as exc:  # noqa: BLE001 - remonté en 404 explicite
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Workflow inconnu ou injoignable"
        ) from exc
    return {"statut": "signal_emis", "decision": decision}


class ValidationRequete(BaseModel):
    """Corps (optionnel) du signal de validation.

    `parent_contrat_id` confirme le rattachement d'un avenant au contrat parent
    proposé à l'étape RAPPROCHEMENT (#33). Absent/null → la pièce reste un contrat
    autonome. Garde-fou §7 : le rattachement n'a lieu QU'À CETTE confirmation.
    """

    parent_contrat_id: str | None = None


@router.post("/contrats/{contrat_id}/valider")
async def valider(
    contrat_id: str,
    requete: ValidationRequete | None = Body(default=None),
    principal: Principal = Depends(get_principal),
    sender: SignalSender = Depends(get_signal_sender),
) -> dict[str, str]:
    """Émet le signal `valider` au workflow en attente → VALIDE→COMMITE (#36).

    Si `parent_contrat_id` est fourni, l'avenant est rattaché à ce parent confirmé
    avant le commit (#33) ; la cible du commit devient alors le parent.
    """
    parent = requete.parent_contrat_id if requete else None
    return await _emettre_decision(contrat_id, "valider", sender, parent)


@router.post("/contrats/{contrat_id}/rejeter")
async def rejeter(
    contrat_id: str,
    principal: Principal = Depends(get_principal),
    sender: SignalSender = Depends(get_signal_sender),
) -> dict[str, str]:
    """Émet le signal `rejeter` au workflow en attente → REJETE_METIER (#36)."""
    return await _emettre_decision(contrat_id, "rejeter", sender)


class ProvenanceSortie(BaseModel):
    """Provenance d'un champ extrait : page + bbox + extrait source (§3)."""

    page: int | None = None
    bbox: list[float] | None = None
    extrait: str | None = None


class ChampARevoir(BaseModel):
    """Un champ d'extraction sous le seuil, enrichi pour la revue HITL (#35).

    Porte tout ce dont l'UI a besoin pour vérifier/corriger : la valeur extraite,
    la confiance et la provenance (page + bbox → surlignage sur l'aperçu PDF).
    """

    cle: str
    valeur: Any = None
    confiance: float
    source: ProvenanceSortie | None = None


class ChampsARevoirReponse(BaseModel):
    """Réponse de la file de revue par champ : aperçu PDF + champs sous le seuil.

    `document_url` = URL présignée GET du PDF source (aperçu + overlay bbox) ;
    ``None`` si la pièce ou S3 sont indisponibles (l'aperçu est best-effort).
    """

    document_url: str | None = None
    champs: list[ChampARevoir] = Field(default_factory=list)


def _champs_extraits(extraction: dict[str, Any]) -> list[ChampARevoir]:
    """Aplatit l'extraction (`domain.Contrat` sérialisé) en champs enrichis.

    Un `Champ` sérialisé est un dict portant une clé `confiance` (float) et,
    typiquement, `valeur` + `source`. On descend récursivement les dicts/listes et
    on retient chaque nœud `Champ`, indexé par son chemin pointé (ex.
    `preavis.delai`, `signataires.0.nom`).
    """
    champs: list[ChampARevoir] = []

    def _descendre(noeud: Any, chemin: str) -> None:
        if isinstance(noeud, dict):
            confiance = noeud.get("confiance")
            if isinstance(confiance, int | float) and not isinstance(confiance, bool):
                champs.append(
                    ChampARevoir(
                        cle=chemin,
                        valeur=noeud.get("valeur"),
                        confiance=float(confiance),
                        source=_source_sortie(noeud.get("source")),
                    )
                )
                return  # nœud Champ : pas de descente sous valeur/source
            for cle, sous in noeud.items():
                _descendre(sous, f"{chemin}.{cle}" if chemin else str(cle))
        elif isinstance(noeud, list):
            for i, sous in enumerate(noeud):
                _descendre(sous, f"{chemin}.{i}" if chemin else str(i))

    _descendre(extraction, "")
    return champs


def _source_sortie(source: Any) -> ProvenanceSortie | None:
    """Mappe une `Provenance` sérialisée (`{page, bbox, extrait}`) vers la sortie API."""
    if not isinstance(source, dict):
        return None
    bbox = source.get("bbox")
    return ProvenanceSortie(
        page=source.get("page"),
        bbox=[float(x) for x in bbox] if isinstance(bbox, list | tuple) else None,
        extrait=source.get("extrait"),
    )


def _presigned_get(settings: Settings, cle_s3: str) -> str | None:
    """URL présignée GET (endpoint PUBLIC) du PDF source, pour l'aperçu HITL.

    Signature SigV4 locale (aucun appel réseau) sur l'hôte que le navigateur
    contactera. Best-effort : toute erreur → ``None`` (le listage des champs ne doit
    pas dépendre de la disponibilité de S3). Import boto3 différé (extra `api`).
    """
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_presign_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        url: str = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": cle_s3},
            ExpiresIn=settings.presign_ttl_seconds,
        )
        return url
    except Exception:  # noqa: BLE001 - aperçu best-effort, jamais bloquant
        return None


@router.get("/contrats/{contrat_id}/champs-a-revoir", response_model=ChampsARevoirReponse)
def champs_a_revoir_contrat(
    contrat_id: uuid.UUID,
    seuil: float = SEUIL_PAR_DEFAUT,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
    settings: Settings = Depends(get_settings),
) -> ChampsARevoirReponse:
    """Champs de l'extraction du contrat sous le seuil de confiance, enrichis (#35).

    Renvoie pour chaque champ sous le seuil sa valeur, sa confiance et sa provenance
    (page + bbox), plus l'URL présignée du PDF source pour l'aperçu + surlignage.
    Lit l'`extraction` de la pièce d'origine du contrat. Sans extraction → champs
    vides (l'URL du document reste fournie si la pièce existe).
    """
    with tenant_session(factory, principal.tenant) as session:
        document = (
            session.query(Document)
            .filter(Document.contrat_id == contrat_id, Document.tenant == principal.tenant)
            .order_by(Document.date_signature)
            .first()
        )
        extraction = document.extraction if document is not None else None
        cle_s3 = document.cle_s3 if document is not None else None

    document_url = _presigned_get(settings, cle_s3) if cle_s3 else None
    if not extraction:
        return ChampsARevoirReponse(document_url=document_url, champs=[])

    champs = [c for c in _champs_extraits(extraction) if c.confiance < seuil]
    champs.sort(key=lambda c: c.cle)
    return ChampsARevoirReponse(document_url=document_url, champs=champs)
