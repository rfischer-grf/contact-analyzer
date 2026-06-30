"""États de la saga d'ingestion (spec §4).

`RECU → CONTROLE → (REJETE_TECHNIQUE) → PARSING → EXTRACTION → RAPPROCHEMENT →
A_VALIDER →` [attente signal `valider`/`rejeter`] `→ VALIDE → COMMITE` / `REJETE_METIER`.
"""

from __future__ import annotations

from enum import StrEnum


class EtatIngestion(StrEnum):
    RECU = "RECU"
    CONTROLE = "CONTROLE"
    REJETE_TECHNIQUE = "REJETE_TECHNIQUE"
    PARSING = "PARSING"
    EXTRACTION = "EXTRACTION"
    RAPPROCHEMENT = "RAPPROCHEMENT"
    A_VALIDER = "A_VALIDER"
    VALIDE = "VALIDE"
    COMMITE = "COMMITE"
    REJETE_METIER = "REJETE_METIER"


#: États terminaux de la saga (plus aucune transition possible).
ETATS_TERMINAUX: frozenset[EtatIngestion] = frozenset(
    {EtatIngestion.COMMITE, EtatIngestion.REJETE_TECHNIQUE, EtatIngestion.REJETE_METIER}
)
