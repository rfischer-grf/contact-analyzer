"""Couche ingestion — première étape du pipeline (spec §2.1, §4).

Contrôles MIME/taille (#17), scan antivirus ClamAV (#18) et dédoublonnage par
SHA256 (#15). Pattern transverse : qualification → résolution → traçabilité.

Garde-fou §4 — séparer infra (retryable) et métier (terminal) :

- `ControleRejete` / `MalwareDetecte` → décision métier terminale (`REJETE_TECHNIQUE`).
- `AntivirusIndisponible` → erreur d'infra, à retenter.
"""

from .antivirus import AntivirusIndisponible, MalwareDetecte, analyser
from .controles import ControleRejete, valider_mime, valider_taille
from .dedup import document_existe

__all__ = [
    "ControleRejete",
    "valider_mime",
    "valider_taille",
    "AntivirusIndisponible",
    "MalwareDetecte",
    "analyser",
    "document_existe",
]
