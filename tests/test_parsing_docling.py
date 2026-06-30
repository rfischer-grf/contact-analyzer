"""Tests du parser réel Docling (#24, #25, #27).

Deux niveaux :

1. **Sans docling installé** — vérifie que `DoclingParser` s'importe (imports
   différés) et qu'il est *structurellement* conforme au `Protocol` `Parser`
   (même signature `parser`), ainsi que le helper `chunks_par_clause` qui
   délègue au découpage par clause de `rag.chunking`.
2. **Avec docling installé** — encadré par `pytest.importorskip("docling")` :
   convertit un vrai PDF à couche texte (OCR jamais sollicité, #25) et vérifie
   blocs + provenance (#26) + markdown.
"""

from __future__ import annotations

import inspect

import pytest

from contract_intelligence.parsing import (
    Bloc,
    DoclingParser,
    DocumentParse,
    Parser,
    chunks_par_clause,
)

# --------------------------------------------------------------------------- #
# 1. Sans docling : importabilité + conformité structurelle au Protocol Parser
# --------------------------------------------------------------------------- #


def test_doclingparser_importable_sans_docling() -> None:
    # L'instanciation ne doit déclencher AUCUN import de docling (imports différés) :
    # le simple fait d'arriver ici (import du module réussi) + instancier le prouve.
    parser = DoclingParser()
    assert isinstance(parser, DoclingParser)


def test_doclingparser_expose_parser_appelable() -> None:
    parser = DoclingParser()
    assert hasattr(parser, "parser")
    assert callable(parser.parser)


def test_doclingparser_signature_conforme_au_protocol() -> None:
    """`DoclingParser.parser` doit reproduire la signature de `Parser.parser`."""
    attendu = inspect.signature(Parser.parser)
    obtenu = inspect.signature(DoclingParser.parser)

    # Mêmes paramètres (hors `self`) avec les mêmes noms et le même mode (kw-only).
    p_attendu = list(attendu.parameters.values())[1:]
    p_obtenu = list(obtenu.parameters.values())[1:]
    assert [p.name for p in p_attendu] == [p.name for p in p_obtenu]
    assert [p.kind for p in p_attendu] == [p.kind for p in p_obtenu]

    # `ocr_si_scanne` est keyword-only avec le même défaut (True).
    assert obtenu.parameters["ocr_si_scanne"].kind is inspect.Parameter.KEYWORD_ONLY
    assert obtenu.parameters["ocr_si_scanne"].default is True
    assert obtenu.parameters["contenu"].annotation == "bytes"


def test_doclingparser_accepte_nom_fichier() -> None:
    parser = DoclingParser(nom_fichier="contrat-acme.pdf")
    assert parser.nom_fichier == "contrat-acme.pdf"
    # Défaut raisonnable utilisé comme indice de format pour le flux en mémoire.
    assert DoclingParser().nom_fichier.endswith(".pdf")


def test_chunks_par_clause_delegue_a_rag_chunking() -> None:
    """Le helper de chunking (#27) délègue à `rag.chunking.decouper_par_clause`."""
    from contract_intelligence.rag import decouper_par_clause

    markdown = (
        "# Contrat de prestation\n\n"
        "Préambule.\n\n"
        "## Article 1 - Objet\n\n"
        "Fourniture de services.\n\n"
        "## Article 2 - Durée\n\n"
        "Conclu pour 24 mois.\n"
    )
    parse = DocumentParse(blocs=[], markdown=markdown)

    obtenu = chunks_par_clause(parse)
    assert obtenu == decouper_par_clause(markdown)

    types = [type_clause for type_clause, _ in obtenu]
    assert types == [
        "Contrat de prestation",
        "Article 1 - Objet",
        "Article 2 - Durée",
    ]
    objet = next(texte for t, texte in obtenu if t == "Article 1 - Objet")
    assert "Fourniture de services" in objet


def test_chunks_par_clause_markdown_vide() -> None:
    assert chunks_par_clause(DocumentParse(blocs=[], markdown="")) == []


# --------------------------------------------------------------------------- #
# 2. Avec docling : conversion réelle (skip propre si la lib est absente)
# --------------------------------------------------------------------------- #


def _pdf_minimal_avec_texte() -> bytes:
    """Construit un PDF mono-page à couche texte (sans dépendance externe).

    PDF 1.4 minimal mais valide : un objet page avec un flux de contenu écrivant
    « CONTRAT DE PRESTATION » via la fonte Helvetica. Suffisant pour que Docling
    détecte une couche texte → l'OCR ne doit pas être sollicité (#25).
    """
    objets: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 68 >>\nstream\nBT /F1 24 Tf 72 760 Td "
        b"(CONTRAT DE PRESTATION) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, corps in enumerate(objets, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode("ascii") + corps + b"\nendobj\n"

    debut_xref = len(pdf)
    pdf += f"xref\n0 {len(objets) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + f"{debut_xref}\n".encode("ascii")
        + b"%%EOF\n"
    )
    return bytes(pdf)


def test_parser_reel_pdf_couche_texte() -> None:
    pytest.importorskip("docling")

    parse = DoclingParser(nom_fichier="contrat.pdf").parser(_pdf_minimal_avec_texte())

    assert isinstance(parse, DocumentParse)
    assert parse.markdown.strip()
    assert "CONTRAT" in parse.markdown.upper()

    # Au moins un bloc porteur de provenance (#26) : page valide + texte non vide.
    assert parse.blocs, "le PDF à couche texte doit produire au moins un bloc"
    for bloc in parse.blocs:
        assert isinstance(bloc, Bloc)
        assert bloc.page >= 1
        assert bloc.texte.strip()
        assert isinstance(bloc.type, str) and bloc.type
        if bloc.bbox is not None:
            x0, y0, x1, y1 = bloc.bbox
            # bbox normalisée (x0 ≤ x1, y0 ≤ y1).
            assert x0 <= x1 and y0 <= y1


def test_parser_reel_ocr_desactivable() -> None:
    """`ocr_si_scanne=False` doit rester accepté et produire un `DocumentParse`."""
    pytest.importorskip("docling")

    parse = DoclingParser().parser(_pdf_minimal_avec_texte(), ocr_si_scanne=False)
    assert isinstance(parse, DocumentParse)
    # PDF à couche texte → le markdown est exploitable même sans OCR.
    assert "CONTRAT" in parse.markdown.upper()
