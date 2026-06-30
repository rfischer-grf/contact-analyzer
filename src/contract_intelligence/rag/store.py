"""Abstraction du vector store + implémentation Fake en mémoire (#49).

Le store réel est **Weaviate** (spec §6, garde-fou §7 : jamais pgvector). On ne
dépend pas du client `weaviate-client` ici : on définit un `Protocol` et une
implémentation `Fake` testable. Le client Weaviate réel relève de TODO(#48).

Isolation multi-tenant (#49) : le store est cloisonné par `tenant`. La RLS
Postgres ne protège PAS Weaviate → l'isolation est explicite dans le store
(`{tenant: {contrat_id: [chunks]}}`) et le `tenant` est injecté côté API, jamais
fourni par le client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Chunk:
    """Un fragment de clause projeté dans le vector store.

    `metadata` porte le filtrage RAG sans repasser par Postgres (spec §6) :
    `contrat_id, tenant, type_clause, date_echeance, fournisseur_siren`.
    `vecteur` est l'embedding BYO (None tant que non vectorisé).
    """

    contrat_id: str
    tenant: str
    type_clause: str
    texte: str
    metadata: dict[str, object] = field(default_factory=dict)
    vecteur: list[float] | None = None


class VectorStore(Protocol):
    """Contrat minimal du vector store (impl. réelle = Weaviate, TODO(#48))."""

    def upsert(self, tenant: str, contrat_id: str, chunks: list[Chunk]) -> None:
        """Réécrit l'ensemble des chunks d'un contrat (delete-then-insert)."""
        ...

    def supprimer(self, tenant: str, contrat_id: str) -> None:
        """Supprime tous les chunks d'un contrat dans le tenant donné."""
        ...

    def rechercher(self, tenant: str, vecteur: list[float], k: int = 5) -> list[Chunk]:
        """Renvoie les `k` chunks les plus proches du vecteur, bornés au tenant."""
        ...


def _similarite(a: list[float], b: list[float]) -> float:
    """Similarité cosinus (0 si l'un des vecteurs est nul ou de dimension nulle)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    produit = sum(x * y for x, y in zip(a, b, strict=True))
    norme_a = sum(x * x for x in a) ** 0.5
    norme_b = sum(y * y for y in b) ** 0.5
    if norme_a == 0.0 or norme_b == 0.0:
        return 0.0
    return produit / (norme_a * norme_b)


class FakeVectorStore:
    """Vector store en mémoire pour le dev et les tests (#49).

    Isolation physique par tenant : `{tenant: {contrat_id: [chunks]}}`. Un tenant
    ne voit jamais les chunks d'un autre tenant (vérifié par test). `rechercher`
    classe par similarité cosinus décroissante, en ne balayant que le tenant.
    """

    def __init__(self) -> None:
        self._par_tenant: dict[str, dict[str, list[Chunk]]] = {}

    def upsert(self, tenant: str, contrat_id: str, chunks: list[Chunk]) -> None:
        # delete-then-insert : idempotent sur contrat_id (gère les avenants).
        tenant_map = self._par_tenant.setdefault(tenant, {})
        tenant_map[contrat_id] = list(chunks)

    def supprimer(self, tenant: str, contrat_id: str) -> None:
        tenant_map = self._par_tenant.get(tenant)
        if tenant_map is not None:
            tenant_map.pop(contrat_id, None)

    def rechercher(self, tenant: str, vecteur: list[float], k: int = 5) -> list[Chunk]:
        tenant_map = self._par_tenant.get(tenant, {})
        candidats = [chunk for chunks in tenant_map.values() for chunk in chunks]
        candidats.sort(
            key=lambda c: _similarite(vecteur, c.vecteur or []),
            reverse=True,
        )
        return candidats[:k]

    # --- Aides de test/réconciliation (hors Protocol) ---

    def contrat_ids(self, tenant: str) -> set[str]:
        """Ensemble des `contrat_id` projetés pour ce tenant (diff de réconciliation)."""
        return set(self._par_tenant.get(tenant, {}).keys())
