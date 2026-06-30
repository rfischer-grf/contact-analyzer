"""Réconciliation périodique Postgres ↔ vector store (#53, spec §6).

Garde-fou (§6) : Postgres = source de vérité, Weaviate = index dérivé. Une
écriture Weaviate peut échouer **après** le commit Postgres ; un diff périodique
des `contrat_id` rattrape l'écart :
- `manquants_dans_store` : présents en base, absents du store → à (re)projeter.
- `orphelins_dans_store` : présents dans le store, absents en base → à purger
  (contrat supprimé, ou écrit dans le mauvais tenant).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contrat
from .store import VectorStore


def _ids_store(store: VectorStore, tenant: str) -> set[str]:
    """Lit les `contrat_id` du store pour un tenant.

    Le `Protocol VectorStore` n'expose pas le listing (Weaviate le fournit
    autrement) ; le Fake offre `contrat_ids`. À défaut, on renvoie un ensemble
    vide (réconciliation dégradée mais sûre).
    """
    lecteur = getattr(store, "contrat_ids", None)
    if callable(lecteur):
        return set(lecteur(tenant))
    return set()


def reconcilier(session: Session, store: VectorStore, tenant: str) -> dict[str, list[str]]:
    """Diff des `contrat_id` Postgres vs store pour un tenant.

    Renvoie `{"manquants_dans_store": [...], "orphelins_dans_store": [...]}`
    (listes triées, ids sous forme de chaînes).
    """
    ids_base = {
        str(cid)
        for cid in session.execute(select(Contrat.id).where(Contrat.tenant == tenant)).scalars()
    }
    ids_store = _ids_store(store, tenant)
    return {
        "manquants_dans_store": sorted(ids_base - ids_store),
        "orphelins_dans_store": sorted(ids_store - ids_base),
    }
