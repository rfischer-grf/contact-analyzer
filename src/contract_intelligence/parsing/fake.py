"""Parser factice — implémentation de `Parser` pour les tests du pipeline aval.

`FakeParser` ne fait **aucun** parsing réel (pas de Docling, pas de RapidOCR,
pas d'I/O réseau) : il décode les octets en UTF-8 et fabrique un bloc par ligne
non vide avec une bbox simulée déterministe et un markdown agrégé. Il sert à
exercer extraction, HITL, chunking et provenance (#26) sans dépendance lourde.

Le parser réel (Docling CPU + OCR conditionnel RapidOCR) reste TODO(#24, #25, #27).
"""

from __future__ import annotations

from .base import Bloc, DocumentParse, Parser


class FakeParser(Parser):
    """`Parser` déterministe pour les tests : texte UTF-8 → blocs + markdown.

    Hypothèse : le `contenu` est du texte UTF-8 (pièce déjà « à couche texte »),
    donc l'OCR n'est jamais sollicité — cohérent avec l'OCR **conditionnel** de
    la spec (§2.2). `ocr_si_scanne` est accepté pour respecter le contrat mais
    n'a pas d'effet ici (pas de vrai OCR — TODO(#25)).

    `largeur` / `hauteur` paramètrent l'échelle des bbox simulées (coordonnées
    en points, origine haut-gauche).
    """

    def __init__(self, largeur: float = 595.0, hauteur: float = 842.0) -> None:
        self.largeur = largeur
        self.hauteur = hauteur

    def parser(self, contenu: bytes, *, ocr_si_scanne: bool = True) -> DocumentParse:
        texte = contenu.decode("utf-8")
        lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]

        blocs: list[Bloc] = []
        # Hauteur de ligne simulée : on empile verticalement les blocs sur la page 1.
        hauteur_ligne = self.hauteur / (len(lignes) + 1) if lignes else self.hauteur
        for i, ligne in enumerate(lignes):
            y0 = i * hauteur_ligne
            bbox = (0.0, y0, self.largeur, y0 + hauteur_ligne)
            blocs.append(Bloc(page=1, bbox=bbox, texte=ligne, type="paragraphe"))

        markdown = "\n\n".join(bloc.texte for bloc in blocs)
        return DocumentParse(blocs=blocs, markdown=markdown)
