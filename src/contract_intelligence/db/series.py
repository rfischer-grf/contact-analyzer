"""Accès aux séries d'indices (`serie_indice`).

`dernier_indice_a_date` = « dernier indice connu à la date D » (sélection de S0/S1).
Les périodes sont stockées au format `YYYY-MM` (comparaison lexicographique = ordre
chronologique).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SerieIndice


def periode_de(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def dernier_indice_a_date(
    session: Session, indice: str, a_la_date: date
) -> tuple[str, float] | None:
    """Dernière valeur publiée dont la période est ≤ au mois de `a_la_date`."""
    cible = periode_de(a_la_date)
    row = session.execute(
        select(SerieIndice.periode, SerieIndice.valeur)
        .where(SerieIndice.indice == indice, SerieIndice.periode <= cible)
        .order_by(SerieIndice.periode.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], float(row[1])


def upsert_serie(
    session: Session, indice: str, periode: str, valeur: float, source: str | None = None
) -> None:
    """Insère ou met à jour une valeur de série (idempotent sur `(indice, periode)`)."""
    existant = session.execute(
        select(SerieIndice).where(SerieIndice.indice == indice, SerieIndice.periode == periode)
    ).scalar_one_or_none()
    if existant is not None:
        existant.valeur = valeur
        if source is not None:
            existant.source = source
    else:
        session.add(SerieIndice(indice=indice, periode=periode, valeur=valeur, source=source))
