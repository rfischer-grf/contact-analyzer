"""Rapprochement des avenants (spec §3.1, tickets #32/#33).

Matching fuzzy avenant→parent (SIREN des parties + référence + objet) pour
l'étape RAPPROCHEMENT de la saga. Proposition seulement : **jamais d'auto-lien**
(garde-fou §7), confirmation dans le gate HITL.
"""

from .matching import (
    Candidat,
    PartiesRef,
    proposer_candidats,
    score_similarite,
)

__all__ = [
    "Candidat",
    "PartiesRef",
    "proposer_candidats",
    "score_similarite",
]
