"""Persistance de l'extraction d'ingestion (#20, #38, spec §2, §3.1).

Trait d'union entre l'activity `persister` de la saga Temporal (worker) et la
couche données. On y matérialise la distinction **document vs contrat** (§3.1) :

- un `Document` = la pièce physique versée (SHA256, clé S3, n° d'avenant, date de
  signature, extraction JSON brute du LLM) ;
- un `Contrat` = l'entité logique portant l'état effectif. À l'ingestion il est
  créé en `etat="A_VALIDER"` : il n'entre ni dans les alertes, ni dans l'ICS, ni
  dans Weaviate tant que le gate HITL n'a pas validé (garde-fou §7).

Garde-fous respectés ici :

- **Idempotence sur le SHA256** : la saga peut rejouer une activity ; ré-appeler
  `persister_extraction` pour un `(tenant, sha256)` déjà connu ne crée pas de
  doublon (contrainte unique `uq_document_tenant_sha256`) — on renvoie le
  `contrat_id` existant et on rafraîchit l'extraction.
- **Jamais d'auto-lien avenant→parent** : on crée toujours un contrat *propre* au
  document. Le rattachement à un parent est une décision confirmée en HITL
  (`rapprocher_avenant` ne fait que *proposer*), jamais posée ici.
- L'état effectif n'est PAS calculé ici : c'est `committer()` qui le folde après
  validation. À l'ingestion, le `Contrat` ne porte que `tenant` + `etat`.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Contrat, Document


def persister_extraction(
    session: Session,
    *,
    tenant: str,
    sha256: str,
    cle_s3: str,
    extraction: dict,
    date_signature: date,
    numero_avenant: int | None = None,
    reference: str | None = None,
) -> uuid.UUID:
    """Persiste l'extraction d'une pièce : crée `Document` + `Contrat(A_VALIDER)`.

    Renvoie l'identifiant du `Contrat` logique lié au document. Idempotent sur
    `(tenant, sha256)` : si la pièce est déjà connue, on rafraîchit son extraction
    et on renvoie le `contrat_id` existant (pas de doublon, pas de second contrat).

    Le contrat est créé en `etat="A_VALIDER"` (gate HITL) : aucune donnée
    `à_valider` n'entre dans les alertes / ICS / Weaviate avant validation (§7).
    """
    existant = session.execute(
        select(Document).where(Document.tenant == tenant, Document.sha256 == sha256)
    ).scalar_one_or_none()

    if existant is not None:
        # Rejeu idempotent : on rafraîchit l'extraction et les métadonnées de pièce
        # sans recréer de contrat (et sans toucher à un éventuel rattachement HITL).
        existant.cle_s3 = cle_s3
        existant.extraction = extraction
        existant.numero_avenant = numero_avenant
        existant.reference = reference
        existant.date_signature = date_signature
        if existant.contrat_id is None:
            contrat = Contrat(tenant=tenant, etat="A_VALIDER", reference=reference)
            session.add(contrat)
            session.flush()
            existant.contrat_id = contrat.id
        session.flush()
        return existant.contrat_id

    contrat = Contrat(tenant=tenant, etat="A_VALIDER", reference=reference)
    session.add(contrat)
    session.flush()  # affecte contrat.id

    document = Document(
        tenant=tenant,
        sha256=sha256,
        cle_s3=cle_s3,
        numero_avenant=numero_avenant,
        reference=reference,
        date_signature=date_signature,
        contrat_id=contrat.id,
        extraction=extraction,
    )
    session.add(document)
    session.flush()
    return contrat.id


def marquer_etat(session: Session, contrat_id: uuid.UUID, etat: str) -> Contrat:
    """Positionne l'`etat` de la saga sur le contrat (ex. ``COMMITE``).

    Lève `ValueError` si le contrat est introuvable. Le suivi fin de la saga
    reste porté par Temporal ; cet `etat` est la projection persistée qui pilote
    notamment la file HITL et les vues (#35).
    """
    contrat = session.get(Contrat, contrat_id)
    if contrat is None:
        raise ValueError(f"Contrat introuvable : {contrat_id}")
    contrat.etat = etat
    session.flush()
    return contrat


def rejeter_metier(session: Session, contrat_id: uuid.UUID) -> Contrat:
    """Marque le contrat comme rejeté en gate HITL (`etat="REJETE_METIER"`).

    Terminal côté saga : un contrat rejeté métier n'est ni committé ni projeté.
    """
    return marquer_etat(session, contrat_id, "REJETE_METIER")
