"""Calculs dérivés du domaine.

`date_limite_denonciation` = échéance − préavis. C'est la **date actionnable**
(critique en tacite reconduction) : elle est CALCULÉE, jamais extraite (spec §2.6, §3).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from .entites import Contrat, UnitePreavis


def _soustraire_mois(d: date, mois: int) -> date:
    """Soustrait `mois` mois à `d` en bornant le jour à la fin du mois cible."""
    index = (d.year * 12 + (d.month - 1)) - mois
    annee, mois_zero = divmod(index, 12)
    mois_cible = mois_zero + 1
    dernier_jour = calendar.monthrange(annee, mois_cible)[1]
    return date(annee, mois_cible, min(d.day, dernier_jour))


def calculer_date_limite_denonciation(echeance: date, delai: int, unite: UnitePreavis) -> date:
    """Échéance − préavis. Gère les unités jours et mois (fins de mois incluses)."""
    if unite == UnitePreavis.jours:
        return echeance - timedelta(days=delai)
    return _soustraire_mois(echeance, delai)


def date_limite_denonciation(contrat: Contrat) -> date | None:
    """Date limite de dénonciation à partir des champs extraits, si disponibles.

    Renvoie ``None`` si l'échéance ou le préavis manquent (un champ à valeur
    ``None`` n'est pas exploitable tant qu'il n'a pas passé le gate HITL).
    """
    if contrat.date_echeance is None or contrat.date_echeance.valeur is None:
        return None
    if contrat.preavis is None:
        return None
    delai = contrat.preavis.delai.valeur
    unite = contrat.preavis.unite.valeur
    if delai is None or unite is None:
        return None
    return calculer_date_limite_denonciation(contrat.date_echeance.valeur, delai, unite)
