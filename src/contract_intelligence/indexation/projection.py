"""Projection tarifaire d'un contrat à une date de révision (spec §2.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..db.models import Contrat
from ..db.series import dernier_indice_a_date
from .moteur import coefficient_raccord_syntec, reviser


@dataclass(frozen=True)
class ResultatRevision:
    p0: float
    s0: float  # après coefficient de raccord éventuel
    s1: float
    coefficient_raccord: float
    p1: float
    periode_s0: str | None
    periode_s1: str


def projeter_tarif(
    session: Session,
    contrat: Contrat,
    date_revision: date,
    part_fixe: float | None = None,
) -> ResultatRevision:
    """Calcule le prix révisé `P1` du contrat à `date_revision`.

    `S0` = `indice_base_valeur` si renseigné, sinon dernier indice à la
    `date_acte_reference`. `S1` = dernier indice à `date_revision`. Le coefficient
    de raccord Syntec est appliqué à `S0` lorsque l'acte de référence est antérieur
    à août 2022.
    """
    if contrat.indice is None or contrat.indice == "aucun":
        raise ValueError("Contrat sans clause d'indexation")
    if contrat.montant is None:
        raise ValueError("Montant (P0) inconnu")

    periode_s0 = contrat.indice_base_periode
    if contrat.indice_base_valeur is not None:
        s0 = float(contrat.indice_base_valeur)
    else:
        if contrat.date_acte_reference is None:
            raise ValueError("Ni S0 stocké ni date d'acte de référence")
        trouve = dernier_indice_a_date(session, contrat.indice, contrat.date_acte_reference)
        if trouve is None:
            raise ValueError("Indice introuvable à la date de l'acte de référence")
        periode_s0, s0 = trouve

    trouve_s1 = dernier_indice_a_date(session, contrat.indice, date_revision)
    if trouve_s1 is None:
        raise ValueError("Indice introuvable à la date de révision")
    periode_s1, s1 = trouve_s1

    coef = coefficient_raccord_syntec(contrat.indice, contrat.date_acte_reference)
    s0_raccorde = s0 * coef
    p0 = float(contrat.montant)
    p1 = reviser(p0, s0_raccorde, s1, part_fixe)

    return ResultatRevision(
        p0=p0,
        s0=s0_raccorde,
        s1=s1,
        coefficient_raccord=coef,
        p1=p1,
        periode_s0=periode_s0,
        periode_s1=periode_s1,
    )
