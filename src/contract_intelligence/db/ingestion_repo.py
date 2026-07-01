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

from .models import Contrat, Document, EvenementAudit


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


def _prochain_numero_avenant(session: Session, parent_id: uuid.UUID) -> int:
    """Prochain n° d'avenant à attribuer dans la chaîne du parent : `max + 1` (≥ 1).

    Le contrat d'origine porte typiquement `numero_avenant = None` ; le premier
    avenant rattaché reçoit donc 1, le suivant 2, etc.
    """
    existants = (
        session.query(Document.numero_avenant).filter(Document.contrat_id == parent_id).all()
    )
    numeros = [n for (n,) in existants if n is not None]
    return (max(numeros) + 1) if numeros else 1


def rattacher_au_parent(
    session: Session,
    *,
    contrat_id: uuid.UUID,
    parent_contrat_id: uuid.UUID,
) -> uuid.UUID:
    """Rattache l'avenant au contrat parent confirmé en gate HITL (#33, spec §3.1).

    Déplace le(s) document(s) du contrat *standalone* `contrat_id` (créé à
    l'ingestion) vers le contrat `parent_contrat_id`, puis supprime le contrat
    standalone devenu orphelin. Renvoie l'id du **parent** : c'est lui qu'il faut
    ensuite `committer()` (son état effectif est refoldé avec l'avenant).

    Le `numero_avenant` d'une pièce sans numéro est attribué à la suite de la chaîne
    du parent (ordre de signature). Le déplacement réassocie chaque pièce au parent
    (`doc.contrat = parent`) AVANT de supprimer le standalone : la pièce n'est jamais
    orpheline, donc la cascade `delete-orphan` ne la supprime pas.

    Garde-fous :
    - **JAMAIS d'auto-lien** (§7) : appelé uniquement à la confirmation HITL.
    - **Multi-tenant** : standalone et parent doivent partager le tenant (sinon
      `ValueError`). Sous RLS PostgreSQL la session est déjà bornée au tenant ; ce
      contrôle explicite garantit le même invariant hors RLS (tests SQLite).
    - **Idempotent** : si le standalone n'existe plus (rejeu de l'activity) ou s'il
      EST le parent, on renvoie simplement le parent sans rien modifier.
    """
    parent = session.get(Contrat, parent_contrat_id)
    if parent is None:
        raise ValueError(f"Contrat parent introuvable : {parent_contrat_id}")
    if contrat_id == parent_contrat_id:
        return parent_contrat_id

    standalone = session.get(Contrat, contrat_id)
    if standalone is None:
        # Rejeu idempotent : le rattachement a déjà eu lieu.
        return parent_contrat_id
    if standalone.tenant != parent.tenant:
        raise ValueError("Rattachement avenant→parent inter-tenant interdit")

    prochain = _prochain_numero_avenant(session, parent.id)
    documents = list(standalone.documents)
    documents_ids = [str(doc.id) for doc in documents]  # capturé avant suppression
    for doc in documents:
        if doc.numero_avenant is None:
            doc.numero_avenant = prochain
            prochain += 1
        # Réassociation par la relation : retire de standalone, rattache au parent.
        # La pièce n'est donc jamais orpheline → pas de suppression en cascade.
        doc.contrat = parent
    session.flush()

    # Le standalone n'a plus de pièce → on le retire (l'identité métier vit au parent).
    session.delete(standalone)

    session.add(
        EvenementAudit(
            tenant=parent.tenant,
            acteur="hitl",
            type_evenement="AVENANT_RATTACHE",
            objet_type="contrat",
            objet_id=str(parent.id),
            payload={
                "contrat_absorbe": str(contrat_id),
                "documents_rattaches": documents_ids,
            },
        )
    )
    session.flush()
    return parent_contrat_id
