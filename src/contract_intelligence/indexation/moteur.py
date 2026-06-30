"""Moteur de révision tarifaire — fonctions pures (spec §2.5).

Formule : `P1 = P0 × (S1/S0)`, ou avec part fixe `a` : `P1 = P0 × (a + (1−a)·S1/S0)`.
`S0` = dernier indice à la date de l'acte de référence ; `S1` = dernier indice à la
date de révision.

Garde-fous (§2.5, §7) :
- **bidirectionnel** : aucune borne — si `S1 < S0`, le prix baisse (la clause
  unidirectionnelle « hausse seule » est réputée non écrite) ;
- **coefficient de raccord Syntec 0,97975** pour tout acte de référence antérieur
  à août 2022 (passage à l'indice révisé).
"""

from __future__ import annotations

from datetime import date

#: Coefficient de raccord Syntec (passage à l'indice révisé d'août 2022).
COEFFICIENT_RACCORD_SYNTEC = 0.97975
#: Tout acte de référence strictement antérieur à cette date subit le raccord.
SEUIL_RACCORD_SYNTEC = date(2022, 8, 1)


def coefficient_raccord_syntec(indice: str, date_acte_reference: date | None) -> float:
    """Renvoie 0,97975 pour un acte de référence Syntec < août 2022, sinon 1,0."""
    if (
        str(indice) == "syntec"
        and date_acte_reference is not None
        and date_acte_reference < SEUIL_RACCORD_SYNTEC
    ):
        return COEFFICIENT_RACCORD_SYNTEC
    return 1.0


def reviser(p0: float, s0: float, s1: float, part_fixe: float | None = None) -> float:
    """Prix révisé `P1`. `part_fixe` = part `a` non indexée dans `[0,1]` (b = 1−a).

    Bidirectionnel : le facteur n'est jamais borné à la hausse.
    """
    if s0 == 0:
        raise ValueError("S0 nul : division impossible")
    ratio = s1 / s0
    if part_fixe is None:
        facteur = ratio
    else:
        if not 0.0 <= part_fixe <= 1.0:
            raise ValueError("part_fixe doit être dans [0, 1]")
        facteur = part_fixe + (1.0 - part_fixe) * ratio
    return p0 * facteur
