"""Service d'embeddings BYO, découplé du store (#51, spec §6).

Garde-fou (§6) : les embeddings sont **BYO** (bge-m3 / e5 local ou Mistral embed)
et **découplés** du vector store — on n'impose aucun couplage entre le calcul du
vecteur et son stockage. Ce module définit le `Protocol`, un `Fake` déterministe
(hash → vecteur de dimension fixe) pour le dev/test, et la fabrique
`embeddeur_par_defaut`. Le backend réel est `embeddeur_http.EmbeddeurHTTP`
(endpoint OpenAI-compatible).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..config import Settings

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


def embeddeur_par_defaut(settings: Settings) -> Embeddeur:
    """Fabrique l'embeddeur par défaut selon la configuration.

    - `embeddings_base_url` défini → `EmbeddeurHTTP` réel (OpenAI-compatible, #51).
    - sinon → `FakeEmbeddeur` déterministe (dev/test, sans réseau), dimensionné
      sur `embeddings_dimension`.

    Import différé de l'impl. HTTP : appeler cette fabrique sans `embeddings_base_url`
    n'importe jamais le module réel (ni `httpx`).
    """
    if settings.embeddings_base_url is not None:
        from .embeddeur_http import EmbeddeurHTTP

        return EmbeddeurHTTP(
            base_url=settings.embeddings_base_url,
            modele=settings.embeddings_modele,
            dimension=settings.embeddings_dimension,
        )
    return FakeEmbeddeur(dimension=settings.embeddings_dimension)
