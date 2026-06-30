"""Couche extraction (epic #63, spec §2.3).

Qualification LLM d'un `Contrat` à partir du markdown Docling. Abstraction
(`Extracteur`) + `FakeExtracteur` testable offline, et seuils de confiance
pilotant la file de revue HITL (#31). Le branchement LLM réel est différé
(cf. `base.Extracteur`, TODO #28/#29/#30).
"""

from .base import Extracteur
from .fake import FakeExtracteur
from .seuils import SEUIL_GENERIQUE, SEUILS_PAR_DEFAUT, champs_sous_seuil

__all__ = [
    "Extracteur",
    "FakeExtracteur",
    "SEUIL_GENERIQUE",
    "SEUILS_PAR_DEFAUT",
    "champs_sous_seuil",
]
