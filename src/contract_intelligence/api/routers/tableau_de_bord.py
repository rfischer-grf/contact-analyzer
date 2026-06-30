"""Agrégats du tableau de bord Clausio (#85).

KPIs calculés sur l'état effectif (tenant/RLS) : volume, répartition par indice,
montants, et comptes d'alertes par palier de `date_limite_denonciation`.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ...alerting import PALIERS
from ...db import Contrat, tenant_session
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/tableau-de-bord", tags=["tableau-de-bord"])


@router.get("")
def tableau(
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
    aujourd_hui: date | None = Query(default=None, description="Date de référence (défaut: today)"),
) -> dict[str, object]:
    reference = aujourd_hui or date.today()
    par_indice: dict[str, int] = {}
    alertes: dict[int, int] = dict.fromkeys(PALIERS, 0)
    montant_total = 0.0
    prochaines: list[tuple[int, dict[str, object]]] = []

    with tenant_session(factory, principal.tenant) as session:
        contrats = (
            session.execute(select(Contrat).where(Contrat.tenant == principal.tenant))
            .scalars()
            .all()
        )
        for c in contrats:
            if c.indice:
                par_indice[c.indice] = par_indice.get(c.indice, 0) + 1
            if c.montant is not None:
                montant_total += float(c.montant)
            if c.date_limite_denonciation is not None:
                jours = (c.date_limite_denonciation - reference).days
                if jours in alertes:
                    alertes[jours] += 1
                if 0 <= jours <= 120:
                    prochaines.append(
                        (
                            jours,
                            {
                                "id": str(c.id),
                                "reference": c.reference,
                                "date_limite_denonciation": c.date_limite_denonciation.isoformat(),
                                "jours_restants": jours,
                            },
                        )
                    )
        nb_contrats = len(contrats)

    prochaines.sort(key=lambda t: t[0])
    return {
        "nb_contrats": nb_contrats,
        "par_indice": par_indice,
        "montant_total": montant_total,
        "alertes": {str(k): v for k, v in alertes.items()},
        "prochaines_echeances": [payload for _, payload in prochaines[:10]],
    }
