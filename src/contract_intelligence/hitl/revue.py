"""File de revue HITL — champs sous le seuil de confiance (#35, spec §2.4).

Les champs dont la confiance passe sous un seuil tombent dans la file de revue :
l'UI affiche le champ + le surlignage de la source pour correction humaine. Ce
module ne porte que la logique pure (sélection des champs à revoir) ; la lecture
de l'extraction et l'exposition HTTP relèvent du routeur API.
"""

from __future__ import annotations

SEUIL_PAR_DEFAUT = 0.8


def champs_a_revoir(
    champs_confiance: dict[str, float], seuil: float = SEUIL_PAR_DEFAUT
) -> list[str]:
    """Renvoie, triés, les noms des champs dont la confiance est < `seuil`.

    `champs_confiance` mappe nom de champ → score de confiance ∈ [0, 1]
    (cf. wrapper `Champ`). Un champ dont la confiance vaut exactement le seuil
    est considéré comme suffisamment fiable et n'est PAS retenu.

    TODO(#35) : la file de revue GLOBALE par contrat `A_VALIDER` (agrégation de
    tous les contrats en attente du tenant) dépend de l'état de la saga Temporal
    et sera exposée plus tard. Ici on ne traite que les champs d'une extraction.
    """
    return sorted(nom for nom, confiance in champs_confiance.items() if confiance < seuil)


def champs_a_revoir_par_seuils(
    champs_confiance: dict[str, float],
    seuils: dict[str, float],
    defaut: float = SEUIL_PAR_DEFAUT,
) -> list[str]:
    """Variante avec seuil par champ : `seuils[nom]`, sinon `defaut`.

    Permet d'exiger une confiance plus élevée sur les champs critiques (préavis,
    date d'échéance) qu'on ne tolère pas mal extraits, sans durcir le seuil global.
    """
    return sorted(
        nom for nom, confiance in champs_confiance.items() if confiance < seuils.get(nom, defaut)
    )
