"""Validation humaine (HITL) — gate non négociable (spec §2.4).

Ce paquet regroupe la logique de la file de revue (#35), la persistance des
corrections alimentant le gold set (#37) et le commit de l'état effectif (#38).
L'émission du signal Temporal valider/rejeter (#36) reste dans le routeur API
(dépendance injectable, import `temporalio` différé).

Invariant : seul un contrat **VALIDÉ** entre dans l'ICS, le périmètre d'alerte et
l'index Weaviate ; aucune donnée `à_valider` ne doit polluer recherche/RAG ni
générer d'alerte.
"""

from .corrections import enregistrer_correction, gold_set
from .revue import (
    ResumeContratARevoir,
    champs_a_revoir,
    champs_a_revoir_par_seuils,
    file_de_revue,
)

__all__ = [
    "ResumeContratARevoir",
    "champs_a_revoir",
    "champs_a_revoir_par_seuils",
    "enregistrer_correction",
    "file_de_revue",
    "gold_set",
]
