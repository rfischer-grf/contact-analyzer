"""Wrapper générique pour tout champ extrait (cf. spec §3).

Invariant : chaque champ extrait porte **valeur + confiance + provenance**.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Provenance(BaseModel):
    """Provenance d'un extrait dans la pièce source (page + bbox + texte brut)."""

    page: int
    bbox: tuple[float, float, float, float] | None = None
    extrait: str  # texte source brut


class Champ(BaseModel, Generic[T]):
    """Valeur extraite + score de confiance ∈ [0,1] + provenance optionnelle."""

    valeur: T | None = None
    confiance: float = Field(ge=0, le=1)
    source: Provenance | None = None
