"""Abstraction de la couche extraction (epic #63, spec §2.3).

L'extraction est la phase de **qualification** du pattern transverse
(qualification → résolution → traçabilité) : à partir du markdown produit par
Docling, on reconstruit un `Contrat` dont chaque champ porte
**valeur + confiance + provenance** (cf. wrapper `Champ`, §3).

Ce module définit le **contrat d'interface** (`Protocol`). La couche data prend
un markdown et rend un `Contrat` validé. Deux implémentations le satisfont :

- `fake.FakeExtracteur` : déterministe, sans LLM ni réseau (tests / démo offline).
- `llm.ExtracteurLLM` : implémentation réelle via **Pydantic AI** — sortie
  structurée re-validée contre le schéma du §3 (`Contrat` + `Champ`) (#28),
  connecteur **Scaleway Generative APIs** (Mistral Small 3.x, souverain EU) ou
  self-host **vLLM** (#29), et stratégie d'entrée markdown complet vs retrieve
  des clauses utiles selon la taille du document (#30). Sa dépendance
  `pydantic_ai` est importée paresseusement → le core reste sans dépendance réseau.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.domain import Contrat


@runtime_checkable
class Extracteur(Protocol):
    """Qualifie un contrat à partir du markdown Docling.

    Toute implémentation doit renvoyer un `Contrat` dont les `Champ` portent
    `valeur + confiance + source` (`Provenance`), de sorte que la couche HITL
    puisse calculer la file de revue (champs sous seuil, cf. `seuils`).
    """

    def extraire(self, markdown: str) -> Contrat:
        """Extrait un `Contrat` structuré (§3) depuis le markdown Docling.

        `markdown` : sortie Docling de la pièce (couche texte + structure,
        provenance page/bbox conservée en amont). Renvoie un `Contrat` validé.
        """
        ...
