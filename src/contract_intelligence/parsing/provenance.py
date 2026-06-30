"""Pont parsing → domaine : conservation de la provenance page + bbox (#26).

Chaque champ extrait porte sa provenance (§3, wrapper `Champ`). Un `Bloc` issu
du parsing en est la source physique : `bloc_vers_provenance` le projette vers
le `Provenance` du domaine sans perte (page + bbox + texte brut), pour le
surlignage de validation HITL et la piste d'audit.
"""

from __future__ import annotations

from contract_intelligence.domain import Provenance

from .base import Bloc


def bloc_vers_provenance(bloc: Bloc) -> Provenance:
    """Projette un `Bloc` du parsing vers la `Provenance` du domaine (#26).

    Conserve fidèlement page + bbox + extrait (texte source brut). Aucune
    transformation : la provenance doit rester traçable jusqu'à la pièce source.
    """
    return Provenance(page=bloc.page, bbox=bloc.bbox, extrait=bloc.texte)
