"""Parser réel Docling (CPU) + OCR conditionnel RapidOCR (#24, #25, #27).

Implémentation concrète du `Protocol` `Parser` (cf. `base.Parser`). Transforme les
octets d'une pièce (PDF, DOCX, image scannée) en blocs structurés porteurs de
provenance (page + bbox, #26) et en markdown agrégé donné en entier à
l'extraction LLM (§2.3).

Garde-fous (§2.2, §7) respectés ici :

- **Docling CPU** par défaut : la latence n'a aucune importance (pipeline async +
  gate HITL de plusieurs jours), seuls comptent coût et throughput. Pas de GPU
  always-on, jamais de colocalisation sur le nœud vLLM (§7).
- **OCR RapidOCR** (ONNX, efficace CPU), **jamais EasyOCR** (torch, réclame GPU).
- **OCR conditionnel** (#25) : RapidOCR n'est activé que si la pièce n'a pas de
  couche texte (PDF scanné). Un PDF déjà à couche texte n'est jamais ré-océrisé.
- **Provenance conservée** (#26) : chaque `Bloc` porte page + bbox + texte + type,
  indispensable au surlignage de validation HITL et à l'audit.

**Imports différés** : `docling` et `rapidocr` ne sont importés que dans le corps
des méthodes — jamais au niveau module. Le module s'importe donc sans ces libs
(extra `parsing` optionnel), ce qui garde le gate vert et permet de tester la
conformité structurelle au `Protocol` sans dépendance lourde.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from contract_intelligence.config import get_settings
from contract_intelligence.rag.chunking import decouper_par_clause

from .base import Bloc, DocumentParse

if TYPE_CHECKING:  # imports purement typage — non exécutés à l'exécution
    from docling.datamodel.document import ConversionResult


class DoclingParser:
    """`Parser` réel : octets → `DocumentParse` via Docling CPU + OCR conditionnel.

    Conforme au `Protocol` `base.Parser` (même signature `parser(...)`). Aucune
    I/O réseau : le parsing opère sur les octets déjà récupérés depuis S3 (Garage)
    par l'activity Temporal.

    `nom_fichier` sert d'indice de format à Docling (extension) lorsqu'on lui
    passe un flux en mémoire ; il n'est jamais lu depuis le disque.
    """

    def __init__(self, nom_fichier: str = "document.pdf") -> None:
        self.nom_fichier = nom_fichier

    def parser(self, contenu: bytes, *, ocr_si_scanne: bool = True) -> DocumentParse:
        """Parse les octets d'une pièce en blocs + markdown (Docling CPU).

        `ocr_si_scanne` active l'OCR **conditionnel** RapidOCR : l'OCR ne tourne
        que si la pièce n'a pas de couche texte (PDF scanné), jamais
        systématiquement. **Jamais EasyOCR, jamais GPU always-on** (§7).

        Le défaut effectif combine l'argument avec `get_settings().docling_ocr_si_scanne` :
        l'OCR n'est tenté que si les deux l'autorisent (l'appelant peut le couper
        ponctuellement sans toucher à la configuration globale).
        """
        ocr_autorise = ocr_si_scanne and get_settings().docling_ocr_si_scanne

        # Premier essai : sans OCR. Si la pièce a une couche texte, on évite tout
        # OCR (conditionnel, #25). Sinon le résultat sera vide → on retente avec OCR.
        resultat = self._convertir(contenu, avec_ocr=False)
        blocs = self._extraire_blocs(resultat)

        if not blocs and ocr_autorise:
            # Pas de couche texte exploitable → pièce probablement scannée :
            # on relance avec RapidOCR activé (et seulement dans ce cas).
            resultat = self._convertir(contenu, avec_ocr=True)
            blocs = self._extraire_blocs(resultat)

        markdown = self._markdown(resultat)
        return DocumentParse(blocs=blocs, markdown=markdown)

    # ----------------------------------------------------------------- internes

    def _convertir(self, contenu: bytes, *, avec_ocr: bool) -> ConversionResult:
        """Convertit les octets via Docling (import différé), OCR au besoin.

        `avec_ocr=False` force `do_ocr=False` (pièce supposée à couche texte) ;
        `avec_ocr=True` active **RapidOCR** (ONNX/CPU), jamais EasyOCR.
        """
        # Imports différés : aucune dépendance Docling au niveau module (gate vert).
        from docling.datamodel.base_models import DocumentStream, InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = avec_ocr
        if avec_ocr:
            # RapidOCR uniquement : ONNX/CPU, jamais EasyOCR (§7).
            pipeline_options.ocr_options = RapidOcrOptions()

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

        # Flux en mémoire : les octets ne touchent jamais le disque (pas de fichier
        # temporaire). `name` fournit l'indice de format (extension) à Docling.
        flux = DocumentStream(name=self.nom_fichier, stream=io.BytesIO(contenu))
        return converter.convert(flux)

    def _extraire_blocs(self, resultat: ConversionResult) -> list[Bloc]:
        """Projette les items Docling en `Bloc` porteurs de provenance (#26).

        Itère les items textuels du document Docling et conserve, par item, son
        texte, son type (label), sa page et sa bbox normalisée (x0, y0, x1, y1).
        Les items sans texte exploitable sont ignorés.
        """
        document = resultat.document
        blocs: list[Bloc] = []

        for item, _niveau in document.iterate_items():
            texte = getattr(item, "text", "") or ""
            if not texte.strip():
                continue

            type_bloc = self._label(item)
            page, bbox = self._provenance(item)
            blocs.append(Bloc(page=page, bbox=bbox, texte=texte, type=type_bloc))

        return blocs

    @staticmethod
    def _label(item: Any) -> str:
        """Renvoie le type/label de l'item Docling sous forme de chaîne stable."""
        label = getattr(item, "label", None)
        if label is None:
            return "paragraphe"
        # `DocItemLabel` est une `str`-Enum : `.value` donne le libellé brut.
        return str(getattr(label, "value", label))

    @staticmethod
    def _provenance(item: Any) -> tuple[int, tuple[float, float, float, float] | None]:
        """Extrait (page, bbox) du premier `ProvenanceItem` d'un item Docling.

        `page_no` Docling est conservé tel quel et seulement borné à >= 1 : la
        provenance reste **1-indexée** (page 1 = première page), cohérente avec
        le `FakeParser` et le surlignage HITL côté front (#26). Page par défaut
        = 1 si la provenance est absente (item sans géométrie).

        La bbox Docling est un `BoundingBox` (l, t, r, b) ; on la normalise en
        (x0, y0, x1, y1) avec x0 ≤ x1 et y0 ≤ y1, quelle que soit l'origine des
        coordonnées (haut- ou bas-gauche selon le backend).
        """
        prov = getattr(item, "prov", None) or []
        if not prov:
            return 1, None

        premier = prov[0]
        page_no = getattr(premier, "page_no", 1)
        page = max(1, int(page_no)) if page_no is not None else 1

        bbox_obj = getattr(premier, "bbox", None)
        if bbox_obj is None:
            return page, None

        gauche = float(getattr(bbox_obj, "l", 0.0))
        haut = float(getattr(bbox_obj, "t", 0.0))
        droite = float(getattr(bbox_obj, "r", 0.0))
        bas = float(getattr(bbox_obj, "b", 0.0))
        x0, x1 = sorted((gauche, droite))
        y0, y1 = sorted((haut, bas))
        return page, (x0, y0, x1, y1)

    @staticmethod
    def _markdown(resultat: ConversionResult) -> str:
        """Exporte le document Docling en markdown structuré (donné au LLM, §2.3)."""
        return resultat.document.export_to_markdown()


def chunks_par_clause(parse: DocumentParse) -> list[tuple[str, str]]:
    """Découpe le markdown d'un `DocumentParse` en `(type_clause, texte)` (#27, §6).

    Délègue à `rag.chunking.decouper_par_clause` (source unique du découpage par
    clause/article, jamais en fenêtre fixe — §6) : on ne duplique pas la logique.
    """
    return decouper_par_clause(parse.markdown)
