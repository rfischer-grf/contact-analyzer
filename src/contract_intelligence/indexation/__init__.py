"""Indexation tarifaire (spec §2.5).

Moteur de révision `P1 = P0 × (S1/S0)` (ou part fixe), coefficient de raccord
Syntec, collecte des séries d'indices et projection tarifaire par contrat.
"""

from .collecteurs import charger_fixtures
from .moteur import (
    COEFFICIENT_RACCORD_SYNTEC,
    coefficient_raccord_syntec,
    reviser,
)
from .projection import ResultatRevision, projeter_tarif

__all__ = [
    "COEFFICIENT_RACCORD_SYNTEC",
    "coefficient_raccord_syntec",
    "reviser",
    "ResultatRevision",
    "projeter_tarif",
    "charger_fixtures",
]
