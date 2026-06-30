"""Couche Parsing (§2.2) — abstraction `Parser` + Fake testable.

Le parser réel Docling CPU + OCR conditionnel RapidOCR reste TODO(#24, #25, #27).
Cf. `base` (contrat), `fake` (tests pipeline), `provenance` (pont vers le domaine, #26).
"""

from .base import Bloc, DocumentParse, Parser
from .fake import FakeParser
from .provenance import bloc_vers_provenance

__all__ = [
    "Bloc",
    "DocumentParse",
    "Parser",
    "FakeParser",
    "bloc_vers_provenance",
]
