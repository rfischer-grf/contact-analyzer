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

Tout est implémenté contre des abstractions (`VectorStore`, `Embeddeur`) :
implémentations réelles `WeaviateVectorStore` (#48) / `EmbeddeurHTTP` (#51) et
`Fake` en mémoire pour le dev/test. Les fabriques `store_par_defaut` /
`embeddeur_par_defaut` choisissent l'impl. réelle ou le `Fake` selon la config.
L'import des impl. réelles (et de leurs clients réseau) est **différé**.
"""

from .chunking import decouper_par_clause
from .embeddeur_http import EmbeddeurHTTP
from .embeddings import Embeddeur, FakeEmbeddeur, embeddeur_par_defaut
from .projection import projeter_contrat
from .recherche import recherche_facette, recherche_semantique
from .reconciliation import reconcilier
from .store import Chunk, FakeVectorStore, VectorStore, store_par_defaut
from .weaviate_store import WeaviateVectorStore

__all__ = [
    "Chunk",
    "VectorStore",
    "FakeVectorStore",
    "WeaviateVectorStore",
    "store_par_defaut",
    "Embeddeur",
    "FakeEmbeddeur",
    "EmbeddeurHTTP",
    "embeddeur_par_defaut",
    "decouper_par_clause",
    "projeter_contrat",
    "recherche_facette",
    "recherche_semantique",
    "reconcilier",
]
