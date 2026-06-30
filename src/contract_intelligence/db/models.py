"""Modèles ORM (spec §3.1, §5).

- `Document` = pièce physique (SHA256, clé S3, n° d'avenant, date de signature, extraction).
- `Contrat` = entité logique portant l'**état effectif calculé** (jamais des champs bruts).
- `EvenementAudit` = piste d'audit append-only (immuabilité garantie par trigger en §migration).
- `SerieIndice` = séries d'indices (indice, periode, valeur), données de référence partagées.

Les colonnes JSON utilisent JSONB sur PostgreSQL et JSON ailleurs (tests SQLite).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

_Json = JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Contrat(Base):
    __tablename__ = "contrat"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant: Mapped[str] = mapped_column(String(64), index=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    # État de la saga d'ingestion (A_VALIDER, COMMITE, REJETE_*) — pilote la file HITL (#35).
    etat: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    # --- État effectif (folé sur la chaîne de documents) ---
    fournisseur_siren: Mapped[str | None] = mapped_column(String(16), nullable=True)
    client_siren: Mapped[str | None] = mapped_column(String(16), nullable=True)
    objet: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_effet: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Calculée (échéance − préavis), jamais extraite — pilote le job d'alerte.
    date_limite_denonciation: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    duree_initiale_mois: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tacite_reconduction: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    preavis_delai: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preavis_unite: Mapped[str | None] = mapped_column(String(8), nullable=True)
    indice: Mapped[str | None] = mapped_column(String(16), nullable=True)
    indice_base_valeur: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)  # S0
    indice_base_periode: Mapped[str | None] = mapped_column(String(7), nullable=True)
    date_acte_reference: Mapped[date | None] = mapped_column(Date, nullable=True)
    montant: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    devise: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # §7 : révision toujours bidirectionnelle dans le moteur.
    bidirectionnelle: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="contrat",
        order_by="Document.date_signature",
        cascade="all, delete-orphan",
    )


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (UniqueConstraint("tenant", "sha256", name="uq_document_tenant_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant: Mapped[str] = mapped_column(String(64), index=True)
    sha256: Mapped[str] = mapped_column(String(64))  # clé canonique
    cle_s3: Mapped[str] = mapped_column(Text)
    numero_avenant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_signature: Mapped[date] = mapped_column(Date)
    # Rattachement avenant→parent : confirmé en HITL, jamais auto-lié (§3.1, §7).
    contrat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contrat.id", ondelete="CASCADE"), nullable=True, index=True
    )
    extraction: Mapped[dict | None] = mapped_column(_Json, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contrat: Mapped[Contrat | None] = relationship(back_populates="documents")


class EvenementAudit(Base):
    __tablename__ = "evenement_audit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant: Mapped[str] = mapped_column(String(64), index=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    acteur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type_evenement: Mapped[str] = mapped_column(String(64))
    objet_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    objet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(_Json, nullable=True)


class Correction(Base):
    """Correction humaine d'un champ extrait — alimente le gold set (spec §2.4, #37).

    Au gate HITL, le relecteur corrige les champs sous le seuil de confiance. Chaque
    correction (ancienne → nouvelle valeur) est consignée par tenant : elle constitue
    la vérité terrain (gold set) qui sert à mesurer/améliorer la qualité d'extraction.
    """

    __tablename__ = "correction"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant: Mapped[str] = mapped_column(String(64), index=True)
    contrat_id: Mapped[str] = mapped_column(String(64), index=True)
    champ: Mapped[str] = mapped_column(String(128))
    ancienne_valeur: Mapped[str | None] = mapped_column(Text, nullable=True)
    nouvelle_valeur: Mapped[str | None] = mapped_column(Text, nullable=True)
    acteur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SerieIndice(Base):
    __tablename__ = "serie_indice"
    __table_args__ = (UniqueConstraint("indice", "periode", name="uq_serie_indice_indice_periode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indice: Mapped[str] = mapped_column(String(16), index=True)
    periode: Mapped[str] = mapped_column(String(7))  # 'YYYY-MM'
    valeur: Mapped[float] = mapped_column(Numeric(12, 4))
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FeedToken(Base):
    """Capability bearer du feed ICS (spec §2.6).

    Pas de RLS : la résolution se fait par `token_hash` (le secret EST l'auth) ;
    le `tenant` porté par la ligne borne ensuite la lecture des contrats.
    On ne stocke que le hash SHA256 du token, jamais le token en clair.
    """

    __tablename__ = "feed_token"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant: Mapped[str] = mapped_column(String(64), index=True)
    sujet: Mapped[str] = mapped_column(String(255))  # utilisateur Keycloak
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoque: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
