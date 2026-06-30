"""Tests de la couche Parsing (§2.2) : Fake, provenance (#26), markdown."""

from __future__ import annotations

from contract_intelligence.domain import Provenance
from contract_intelligence.parsing import (
    Bloc,
    DocumentParse,
    FakeParser,
    bloc_vers_provenance,
)

_TEXTE = "CONTRAT DE PRESTATION\n\nEntre la société ACME SAS\net la société Client SA\n"


def test_fakeparser_produit_blocs_avec_provenance() -> None:
    parse = FakeParser().parser(_TEXTE.encode("utf-8"))

    assert isinstance(parse, DocumentParse)
    # Un bloc par ligne NON vide (la ligne vide est ignorée).
    assert len(parse.blocs) == 3
    for bloc in parse.blocs:
        assert isinstance(bloc, Bloc)
        assert bloc.page == 1
        assert bloc.bbox is not None and len(bloc.bbox) == 4
        assert bloc.texte.strip()
        assert bloc.type == "paragraphe"

    assert parse.blocs[0].texte == "CONTRAT DE PRESTATION"


def test_fakeparser_markdown_non_vide() -> None:
    parse = FakeParser().parser(_TEXTE.encode("utf-8"))

    assert parse.markdown
    assert "ACME SAS" in parse.markdown
    # Le markdown agrège bien tous les blocs.
    for bloc in parse.blocs:
        assert bloc.texte in parse.markdown


def test_fakeparser_document_vide() -> None:
    parse = FakeParser().parser(b"   \n\n  \n")

    assert parse.blocs == []
    assert parse.markdown == ""


def test_fakeparser_ocr_si_scanne_sans_effet() -> None:
    # OCR conditionnel (TODO #25) : le Fake ignore le flag, résultat identique.
    octets = _TEXTE.encode("utf-8")
    assert FakeParser().parser(octets, ocr_si_scanne=False) == FakeParser().parser(
        octets, ocr_si_scanne=True
    )


def test_bloc_vers_provenance_conserve_page_bbox_extrait() -> None:
    bloc = Bloc(page=3, bbox=(0.0, 10.0, 595.0, 42.0), texte="Préavis : 3 mois", type="paragraphe")

    prov = bloc_vers_provenance(bloc)

    assert isinstance(prov, Provenance)
    assert prov.page == 3
    assert prov.bbox == (0.0, 10.0, 595.0, 42.0)
    assert prov.extrait == "Préavis : 3 mois"


def test_bloc_vers_provenance_bbox_optionnelle() -> None:
    bloc = Bloc(page=1, bbox=None, texte="couche texte sans géométrie", type="paragraphe")

    prov = bloc_vers_provenance(bloc)

    assert prov.bbox is None
    assert prov.extrait == "couche texte sans géométrie"


def test_provenance_issue_du_fakeparser_traçable() -> None:
    parse = FakeParser().parser(_TEXTE.encode("utf-8"))

    provenances = [bloc_vers_provenance(b) for b in parse.blocs]

    assert all(p.page == 1 for p in provenances)
    assert provenances[0].extrait == "CONTRAT DE PRESTATION"
