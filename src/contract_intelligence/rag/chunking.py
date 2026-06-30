"""Découpage par clause/article (#50, spec §6).

Garde-fou (§6) : chunking **par clause/article** (via la structure Docling), PAS
en fenêtre fixe. On découpe le markdown sur ses frontières structurelles :
- titres markdown (`#`, `##`, `###`, …),
- en-têtes « Article N » (avec variantes : « ARTICLE 1 - Objet », « Article 2. »).

Chaque chunk est typé par son titre (`type_clause`), exploité ensuite comme
métadonnée de filtrage RAG (spec §6).
"""

from __future__ import annotations

import re

# Titre markdown : un à six dièses puis le libellé.
_RE_TITRE_MD = re.compile(r"^\s{0,3}#{1,6}\s+(?P<titre>.+?)\s*#*\s*$")
# En-tête « Article N … » (insensible à la casse), éventuellement numéroté/ponctué.
_RE_ARTICLE = re.compile(r"^\s*(?P<titre>article\s+\d+\b.*)$", re.IGNORECASE)

# Type de clause par défaut pour le texte précédant tout titre (préambule).
TYPE_PREAMBULE = "préambule"


def _titre_de_ligne(ligne: str) -> str | None:
    """Renvoie le libellé de titre si la ligne est une frontière de clause."""
    m = _RE_TITRE_MD.match(ligne)
    if m is not None:
        return m.group("titre").strip()
    m = _RE_ARTICLE.match(ligne)
    if m is not None:
        return m.group("titre").strip()
    return None


def decouper_par_clause(markdown: str) -> list[tuple[str, str]]:
    """Découpe un markdown en `(type_clause, texte)` sur les titres/articles.

    Le `type_clause` est le libellé du titre ; le `texte` est le titre suivi de
    son corps jusqu'au titre suivant. Le texte précédant le premier titre forme
    un chunk « préambule ». Les chunks vides (titre sans corps ni libellé utile)
    sont conservés tant qu'ils portent un type, mais le préambule vide est ignoré.
    """
    lignes = markdown.splitlines()
    chunks: list[tuple[str, str]] = []

    type_courant = TYPE_PREAMBULE
    corps: list[str] = []

    def _flush() -> None:
        texte = "\n".join(corps).strip()
        # On ignore un préambule vide ; on garde une clause titrée même courte.
        if type_courant == TYPE_PREAMBULE and not texte:
            return
        chunks.append((type_courant, texte))

    for ligne in lignes:
        titre = _titre_de_ligne(ligne)
        if titre is not None:
            _flush()
            type_courant = titre
            corps = [ligne.strip()]
        else:
            corps.append(ligne)

    _flush()
    return chunks
