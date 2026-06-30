"""Feed ICS de visibilité (spec §2.6).

1 VEVENT par échéance / date limite de dénonciation (et date de révision à venir).
Garde-fous : **pas de `VALARM`** (iCal = visibilité, pas un mécanisme d'alerte) ;
le feed ne contient que **dates + intitulé**, jamais le contenu des clauses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contrat


@dataclass(frozen=True)
class EvenementCalendrier:
    uid: str
    jour: date
    intitule: str


def _echap(texte: str) -> str:
    return texte.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def generer_ics(evenements: list[EvenementCalendrier], nom: str = "Contrats CLM") -> str:
    """Sérialise les évènements en calendrier iCalendar (RFC 5545), sans `VALARM`."""
    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CLM//Contract Intelligence//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_echap(nom)}",
    ]
    for ev in evenements:
        jour = ev.jour.strftime("%Y%m%d")
        lignes += [
            "BEGIN:VEVENT",
            f"UID:{ev.uid}",
            f"DTSTART;VALUE=DATE:{jour}",
            f"DTEND;VALUE=DATE:{jour}",
            f"SUMMARY:{_echap(ev.intitule)}",
            "END:VEVENT",
        ]
    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes) + "\r\n"


def feed_pour_tenant(session: Session, tenant: str) -> list[EvenementCalendrier]:
    """Construit les évènements du feed d'un tenant à partir de l'état effectif."""
    contrats = session.execute(select(Contrat).where(Contrat.tenant == tenant)).scalars().all()
    evenements: list[EvenementCalendrier] = []
    for c in contrats:
        intitule_base = c.reference or str(c.id)
        if c.date_echeance is not None:
            evenements.append(
                EvenementCalendrier(
                    uid=f"{c.id}-echeance",
                    jour=c.date_echeance,
                    intitule=f"Échéance — {intitule_base}",
                )
            )
        if c.date_limite_denonciation is not None:
            evenements.append(
                EvenementCalendrier(
                    uid=f"{c.id}-denonciation",
                    jour=c.date_limite_denonciation,
                    intitule=f"Date limite de dénonciation — {intitule_base}",
                )
            )
    return evenements
