"""Abstraction de la couche extraction (epic #63, spec §2.3).

L'extraction est la phase de **qualification** du pattern transverse
(qualification → résolution → traçabilité) : à partir du markdown produit par
Docling, on reconstruit un `Contrat` dont chaque champ porte
**valeur + confiance + provenance** (cf. wrapper `Champ`, §3).

Ce module ne définit que le **contrat d'interface** (`Protocol`). La couche
data prend un markdown et rend un `Contrat` validé ; le branchement réel sur un
LLM relève des tickets suivants — tenus hors de cette première itération qui
livre l'abstraction et un `FakeExtracteur` testable, sans dépendance réseau.

TODO(#28) : implémentation réelle via **Pydantic AI** — sortie structurée
    validée contre le schéma du §3 (`Contrat` + `Champ`), avec re-validation
    Pydantic v2 du JSON renvoyé par le modèle.
TODO(#29) : connecteur **Scaleway Generative APIs** (Mistral Small 3.x, souverain
    EU) ou self-host **vLLM** ; le 7B local réservé au pré-filtrage/classification.
TODO(#30) : stratégie d'entrée — donner le **markdown Docling complet** pour un
    contrat de 5–30 pages, sinon **retrieve** des clauses utiles (parties, durée,
    résiliation, indexation) avant extraction si le document est volumineux.
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
