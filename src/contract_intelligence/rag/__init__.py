"""Recherche & RAG (Weaviate) — epic #68 (spec §6).

Garde-fous (§6, §7) :
- Weaviate est le **seul** vector store (pas de pgvector). Postgres = source de
  vérité, Weaviate = index dérivé, jamais l'inverse.
- Écriture Weaviate **uniquement après COMMITE** ; idempotente sur `contrat_id`
  (delete-then-insert) pour gérer les avenants qui réécrivent l'état effectif.
- Isolation multi-tenant côté store : `tenant` injecté côté API, **jamais fourni
  par le client** (la RLS Postgres ne protège pas le vector store).
- Recherche par **facette extraite** = SQL `WHERE` sur Postgres (PAS du vectoriel).
  Le vectoriel sert uniquement au sémantique sur le corps des clauses et au RAG.
- Embeddings **BYO**, découplés du store.

Ici tout est implémenté contre des abstractions (`VectorStore`, `Embeddeur`) avec
une implémentation `Fake` en mémoire. Le client Weaviate réel + le câblage de la
saga sont laissés en TODO(#48).
"""

from .chunking import decouper_par_clause
from .embeddings import Embeddeur, FakeEmbeddeur
from .projection import projeter_contrat
from .recherche import recherche_facette, recherche_semantique
from .reconciliation import reconcilier
from .store import Chunk, FakeVectorStore, VectorStore

__all__ = [
    "Chunk",
    "VectorStore",
    "FakeVectorStore",
    "Embeddeur",
    "FakeEmbeddeur",
    "decouper_par_clause",
    "projeter_contrat",
    "recherche_facette",
    "recherche_semantique",
    "reconcilier",
]
