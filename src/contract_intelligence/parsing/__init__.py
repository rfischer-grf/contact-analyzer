"""Couche Parsing (§2.2) — abstraction `Parser`, Fake testable et Docling réel.

Cf. `base` (contrat `Parser` + dataclasses), `fake` (tests pipeline),
`docling_parser` (réel : Docling CPU + OCR conditionnel RapidOCR, #24/#25/#27) et
`provenance` (pont vers le domaine, #26).

`DoclingParser` s'importe sans la lib `docling` (imports différés dans les
méthodes) : seul l'appel réel à `parser()` requiert l'extra `parsing`.
"""

from .base import Bloc, DocumentParse, Parser
from .docling_parser import DoclingParser, chunks_par_clause
from .fake import FakeParser
from .provenance import bloc_vers_provenance

__all__ = [
    "Bloc",
    "DocumentParse",
    "Parser",
    "FakeParser",
    "DoclingParser",
    "chunks_par_clause",
    "bloc_vers_provenance",
]
