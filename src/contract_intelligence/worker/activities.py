"""Activities du pipeline d'ingestion (spec §2, §4).

Squelette : signatures et découpage en place ; l'implémentation relève des tickets
dédiés. Garde-fou (§4) : une erreur d'infra est *retryable*, une décision métier
(malware détecté) est *terminale* (non-retryable).
"""

from __future__ import annotations

from temporalio import activity


@activity.defn
async def controle_et_av(cle: str) -> bool:
    """Contrôles MIME/taille (#17) + scan antivirus ClamAV (#18). Stub : accepte."""
    # TODO(#17,#18) : MIME/taille + clamd ; malware → erreur non-retryable.
    return True


@activity.defn
async def parser_document(cle: str) -> dict:
    """Parsing Docling CPU + OCR RapidOCR conditionnel + provenance (#24–#27)."""
    raise NotImplementedError("Docling (#24)")


@activity.defn
async def extraire_champs(markdown: str) -> dict:
    """Extraction LLM structurée (Pydantic AI) (#28–#31)."""
    raise NotImplementedError("Extraction LLM (#28)")


@activity.defn
async def rapprocher_avenant(contrat_id: str) -> dict:
    """Proposition de rattachement avenant→parent (jamais d'auto-lien) (#32)."""
    raise NotImplementedError("Rapprochement (#32)")


@activity.defn
async def committer(contrat_id: str) -> str:
    """Rejoue la chaîne de documents et réécrit l'état effectif (#38)."""
    raise NotImplementedError("Commit état effectif (#38)")


@activity.defn
async def projeter_weaviate(contrat_id: str) -> None:
    """Projection Weaviate idempotente — UNIQUEMENT après COMMITE (#48)."""
    raise NotImplementedError("Projection Weaviate (#48)")
