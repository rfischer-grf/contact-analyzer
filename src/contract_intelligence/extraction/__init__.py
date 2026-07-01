"""Couche extraction (epic #63, spec §2.3).

Qualification LLM d'un `Contrat` à partir du markdown Docling. Abstraction
(`Extracteur`), `FakeExtracteur` testable offline, et `ExtracteurLLM` réel
(Pydantic AI + sortie structurée §3 ; #28/#29/#30) dont la dépendance
`pydantic_ai` est importée paresseusement. Les seuils de confiance pilotent la
file de revue HITL (#31).
"""

from .base import Extracteur
from .fake import FakeExtracteur
from .llm import ExtracteurLLM, retrieve_clauses_utiles
from .seuils import SEUIL_GENERIQUE, SEUILS_PAR_DEFAUT, champs_sous_seuil

__all__ = [
    "Extracteur",
    "FakeExtracteur",
    "ExtracteurLLM",
    "retrieve_clauses_utiles",
    "SEUIL_GENERIQUE",
    "SEUILS_PAR_DEFAUT",
    "champs_sous_seuil",
]
