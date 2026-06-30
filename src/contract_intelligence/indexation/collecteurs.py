"""Collecte des séries d'indices (spec §2.5).

- **INSEE BDM** (ILAT/ILC/ICC + INSEE) : API SDMX 2.1 REST, par `idbank` (#39).
- **Syntec** : pas d'API → scrape mensuel de syntec.fr (#40).
- **Dev** : `charger_fixtures` injecte des valeurs figées (substitution §5).

Les collecteurs réseau sont des squelettes (non sollicités par les tests) ; le
coefficient de raccord Syntec s'applique au calcul de révision, pas à la collecte.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from ..db.series import upsert_serie

# Points d'accès des collecteurs réels (implémentation à venir).
INSEE_BDM_DATAFLOW = "ILC-ILAT-ICC"
SYNTEC_URL = "https://syntec.fr/indice-syntec/"


def charger_fixtures(session: Session, chemin: str | Path) -> int:
    """Charge des séries figées `{indice: {periode: valeur}}`. Renvoie le nb de points."""
    data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    n = 0
    for indice, serie in data.items():
        if indice.startswith("_") or not isinstance(serie, dict):
            continue  # clés de métadonnées (ex. "_comment")
        for periode, valeur in serie.items():
            upsert_serie(
                session, indice=indice, periode=periode, valeur=float(valeur), source="fixture"
            )
            n += 1
    return n


def collecter_insee(session: Session, idbank: str, indice: str) -> int:
    """Collecte INSEE BDM (SDMX 2.1) par `idbank` → `serie_indice` (#39)."""
    raise NotImplementedError("Collecteur INSEE BDM (#39)")


def collecter_syntec(session: Session) -> int:
    """Scrape la valeur mensuelle Syntec depuis syntec.fr → `serie_indice` (#40)."""
    raise NotImplementedError("Collecteur Syntec (#40)")
