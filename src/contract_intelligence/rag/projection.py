"""Projection d'un contrat vers le vector store (#50, #48, spec §6).

Garde-fous (§6, §7) :
- Écriture **uniquement après COMMITE** : `projeter_contrat` est appelée par
  l'activity de projection en fin de saga (delete-then-insert). La logique est
  écrite contre un `VectorStore` abstrait : `WeaviateVectorStore` en réel (#48),
  `FakeVectorStore` en test — même contrat, même idempotence.
- **Idempotent sur `contrat_id`** : `upsert` réécrit l'intégralité des chunks du
  contrat → re-projeter ne crée pas de doublon (gère les avenants qui réécrivent
  l'état effectif).
- Chunking par clause (jamais en fenêtre fixe) ; chaque chunk porte les
  métadonnées de filtrage RAG `{contrat_id, tenant, type_clause, date_echeance,
  fournisseur_siren}`, lues sur la ligne `Contrat` (Postgres = source de vérité).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..db.models import Contrat
from .chunking import decouper_par_clause
from .embeddings import Embeddeur
from .store import Chunk, VectorStore


def projeter_contrat(
    store: VectorStore,
    embeddeur: Embeddeur,
    session: Session,
    tenant: str,
    contrat_id: str,
    markdown: str,
) -> int:
    """Projette l'état effectif d'un contrat dans le vector store.

    Appelée **uniquement après COMMITE** (activity de projection en fin de saga).
    Découpe `markdown` par clause, vectorise (embeddings BYO), construit les
    métadonnées par chunk depuis la ligne `Contrat`, puis fait un
    **delete-then-insert** idempotent sur `contrat_id`.

    Renvoie le nombre de chunks projetés.
    """
    contrat = session.get(Contrat, uuid.UUID(contrat_id))
    if contrat is None or contrat.tenant != tenant:
        # Sécurité : on ne projette jamais un contrat hors du tenant attendu.
        raise ValueError("Contrat introuvable pour ce tenant")

    clauses = decouper_par_clause(markdown)
    if not clauses:
        # Rien à indexer : on purge tout de même pour rester idempotent.
        store.supprimer(tenant, contrat_id)
        return 0

    date_echeance = contrat.date_echeance.isoformat() if contrat.date_echeance else None
    base_metadata: dict[str, object] = {
        "contrat_id": contrat_id,
        "tenant": tenant,
        "date_echeance": date_echeance,
        "fournisseur_siren": contrat.fournisseur_siren,
    }

    textes = [texte for _type, texte in clauses]
    vecteurs = embeddeur.vectoriser(textes)

    chunks = [
        Chunk(
            contrat_id=contrat_id,
            tenant=tenant,
            type_clause=type_clause,
            texte=texte,
            metadata={**base_metadata, "type_clause": type_clause},
            vecteur=vecteur,
        )
        for (type_clause, texte), vecteur in zip(clauses, vecteurs, strict=True)
    ]

    # delete-then-insert via upsert (réécrit l'ensemble) → idempotent.
    store.upsert(tenant, contrat_id, chunks)
    return len(chunks)
