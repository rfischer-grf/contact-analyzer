"""Service d'embeddings BYO, découplé du store (#51, spec §6).

Garde-fou (§6) : les embeddings sont **BYO** (bge-m3 / e5 local ou Mistral embed)
et **découplés** du vector store — on n'impose aucun couplage entre le calcul du
vecteur et son stockage. On définit ici un `Protocol` et une implémentation
déterministe (hash → vecteur de dimension fixe) pour le dev et les tests. Le
backend d'embeddings réel relève d'un ticket dédié.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

DIMENSION_PAR_DEFAUT = 32


class Embeddeur(Protocol):
    """Calcule les vecteurs d'une liste de textes (1 vecteur par texte)."""

    def vectoriser(self, textes: list[str]) -> list[list[float]]: ...


class FakeEmbeddeur:
    """Embeddeur déterministe pour dev/tests : hash → vecteur de dimension fixe.

    Déterministe (même texte → même vecteur) et borné (composantes normalisées
    dans [0, 1)) : suffisant pour exercer la recherche sémantique sans dépendance
    réseau ni modèle. Aucune sémantique réelle — uniquement de la reproductibilité.
    """

    def __init__(self, dimension: int = DIMENSION_PAR_DEFAUT) -> None:
        self.dimension = dimension

    def _vecteur(self, texte: str) -> list[float]:
        # Étire un digest SHA256 sur `dimension` octets de façon déterministe.
        composantes: list[float] = []
        compteur = 0
        while len(composantes) < self.dimension:
            digest = hashlib.sha256(f"{compteur}:{texte}".encode()).digest()
            for octet in digest:
                composantes.append(octet / 255.0)
                if len(composantes) == self.dimension:
                    break
            compteur += 1
        return composantes

    def vectoriser(self, textes: list[str]) -> list[list[float]]:
        return [self._vecteur(texte) for texte in textes]
