"""Job d'alerte quotidien (spec §2.6, §7).

Scanne l'**état effectif** (table `contrat`, alimentée uniquement après validation
+ COMMITE) : `date_limite_denonciation - today IN (90, 60, 30, 7)` → mail + audit.
**Pas** de timer Temporal ni de `VALARM` : c'est un job loggé (preuve d'envoi).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contrat, EvenementAudit
from .mailer import Mailer

PALIERS = (90, 60, 30, 7)


@dataclass(frozen=True)
class Alerte:
    contrat_id: str
    tenant: str
    date_limite_denonciation: date
    jours_restants: int


def scanner_alertes(
    session: Session, aujourd_hui: date, paliers: tuple[int, ...] = PALIERS
) -> list[Alerte]:
    """Contrats dont la date limite de dénonciation tombe sur un palier d'alerte."""
    contrats = (
        session.execute(select(Contrat).where(Contrat.date_limite_denonciation.is_not(None)))
        .scalars()
        .all()
    )
    alertes: list[Alerte] = []
    for c in contrats:
        assert c.date_limite_denonciation is not None
        jours = (c.date_limite_denonciation - aujourd_hui).days
        if jours in paliers:
            alertes.append(
                Alerte(
                    contrat_id=str(c.id),
                    tenant=c.tenant,
                    date_limite_denonciation=c.date_limite_denonciation,
                    jours_restants=jours,
                )
            )
    return alertes


def executer_job_alertes(
    session: Session,
    aujourd_hui: date,
    mailer: Mailer,
    destinataires: dict[str, str] | None = None,
) -> list[Alerte]:
    """Envoie un mail par alerte et journalise l'envoi (preuve, traçabilité)."""
    alertes = scanner_alertes(session, aujourd_hui)
    for a in alertes:
        destinataire = (destinataires or {}).get(a.tenant, f"alertes+{a.tenant}@example.test")
        sujet = f"[CLM] Dénonciation à J-{a.jours_restants} — contrat {a.contrat_id}"
        corps = (
            f"Date limite de dénonciation : {a.date_limite_denonciation.isoformat()} "
            f"(J-{a.jours_restants}). Au-delà, reconduction tacite."
        )
        mailer.envoyer(destinataire, sujet, corps)
        session.add(
            EvenementAudit(
                tenant=a.tenant,
                type_evenement="ALERTE_ENVOYEE",
                objet_type="contrat",
                objet_id=a.contrat_id,
                payload={
                    "palier": a.jours_restants,
                    "date_limite_denonciation": a.date_limite_denonciation.isoformat(),
                    "destinataire": destinataire,
                },
            )
        )
    session.flush()
    return alertes
