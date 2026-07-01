"""Abstraction de la couche Parsing (cf. spec §2.2 — Parsing/Docling).

Cette couche transforme les octets d'une pièce (PDF, image scannée) en blocs
structurés porteurs de provenance (page + bbox) et en markdown, consommés en
aval par l'extraction LLM (§2.3) et le chunking par clause (§6).

On livre ici le `Protocol` stable (`Parser`) et ses dataclasses (`Bloc`,
`DocumentParse`). Deux implémentations le réalisent : `fake.FakeParser` (tests
pipeline, sans dépendance lourde) et `docling_parser.DoclingParser` (réel,
Docling CPU + OCR conditionnel RapidOCR). Garde-fous (§2.2, §7) tenus par
l'implémentation réelle :

- Docling CPU (#24) : la latence n'importe pas (pipeline async + gate HITL de
  plusieurs jours), seuls comptent coût et throughput. Pas de GPU always-on ;
  GPU seulement en pool L4 éphémère scale-to-zero, jamais colocalisé sur le
  nœud vLLM.
- OCR conditionnel **RapidOCR** (ONNX, efficace CPU), uniquement si la pièce n'a
  pas de couche texte (PDF scanné) — #25. **Jamais EasyOCR** (torch, réclame GPU).
- Markdown structuré + chunking par clause/article (#27, délégué à `rag.chunking`).
- Conservation de la provenance (page + bbox) de chaque bloc (#26), indispensable
  au surlignage de validation HITL et à l'audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Bloc:
    """Bloc structuré issu du parsing, porteur de sa provenance (#26).

    `bbox` (x0, y0, x1, y1) est optionnelle : un bloc peut provenir d'une couche
    texte sans géométrie exploitable. `type` qualifie le bloc (ex. ``paragraphe``,
    ``titre``, ``tableau``) pour le chunking par clause en aval (§6).
    """

    page: int
    bbox: tuple[float, float, float, float] | None
    texte: str
    type: str


@dataclass
class DocumentParse:
    """Résultat du parsing d'une pièce : blocs + provenance et markdown agrégé.

    Le markdown est donné en entier à l'extraction LLM (§2.3) ; les `blocs`
    portent la provenance pour le surlignage HITL et le chunking RAG (§6).
    """

    blocs: list[Bloc] = field(default_factory=list)
    markdown: str = ""


class Parser(Protocol):
    """Contrat de la couche Parsing (octets → `DocumentParse`).

    Implémentations : `fake.FakeParser` (tests pipeline) et
    `docling_parser.DoclingParser` (réel, Docling CPU). Pas d'I/O réseau : le
    parsing opère sur les octets déjà récupérés depuis S3 (Garage) par l'activity
    Temporal.
    """

    def parser(self, contenu: bytes, *, ocr_si_scanne: bool = True) -> DocumentParse:
        """Parse les octets d'une pièce en blocs + markdown.

        `ocr_si_scanne` active l'OCR **conditionnel** RapidOCR (#25) : l'OCR ne
        tourne que si la pièce n'a pas de couche texte (PDF scanné), jamais
        systématiquement. **Jamais EasyOCR, jamais GPU always-on** (§7).
        """
        ...
