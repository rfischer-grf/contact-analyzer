"""Tests du découpage par clause/article (#50).

Garde-fou (§6) : découpage par titre/article, jamais en fenêtre fixe.
"""

from __future__ import annotations

from contract_intelligence.rag import decouper_par_clause


def test_decoupe_par_titres_markdown() -> None:
    markdown = """# Contrat de prestation

Préambule entre les parties.

## Article 1 - Objet

L'objet du contrat est la fourniture de services.

## Article 2 - Durée

Le contrat est conclu pour 24 mois.

## Indexation

Indice Syntec, révision annuelle.
"""
    chunks = decouper_par_clause(markdown)
    types = [type_clause for type_clause, _ in chunks]

    assert types == [
        "Contrat de prestation",
        "Article 1 - Objet",
        "Article 2 - Durée",
        "Indexation",
    ]
    # Chaque chunk porte son corps (pas une fenêtre fixe).
    objet = next(texte for t, texte in chunks if t == "Article 1 - Objet")
    assert "fourniture de services" in objet
    duree = next(texte for t, texte in chunks if t == "Article 2 - Durée")
    assert "24 mois" in duree


def test_decoupe_articles_sans_diese() -> None:
    markdown = """Article 1. Objet
La société fournit des prestations.

ARTICLE 2 - Résiliation
Préavis de trois mois.
"""
    chunks = decouper_par_clause(markdown)
    types = [t for t, _ in chunks]
    assert types == ["Article 1. Objet", "ARTICLE 2 - Résiliation"]
    assert "prestations" in chunks[0][1]
    assert "Préavis" in chunks[1][1]


def test_preambule_avant_premier_titre() -> None:
    markdown = """Texte introductif hors clause.

# Article 1 - Objet
Corps.
"""
    chunks = decouper_par_clause(markdown)
    assert chunks[0][0] == "préambule"
    assert "introductif" in chunks[0][1]
    assert chunks[1][0] == "Article 1 - Objet"


def test_preambule_vide_ignore() -> None:
    markdown = "# Article 1 - Objet\nCorps unique."
    chunks = decouper_par_clause(markdown)
    assert len(chunks) == 1
    assert chunks[0][0] == "Article 1 - Objet"


def test_markdown_vide() -> None:
    assert decouper_par_clause("") == []
    assert decouper_par_clause("   \n  ") == []
