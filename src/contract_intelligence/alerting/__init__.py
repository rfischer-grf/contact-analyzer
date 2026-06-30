"""Alerting & visibilité (spec §2.6).

- Job quotidien qui scanne l'état effectif (`date_limite_denonciation`) et notifie.
- Feed ICS de visibilité (pas de `VALARM`), protégé par un capability token.
"""

from .capability import creer_token, resoudre_token, revoquer, roter
from .ics import EvenementCalendrier, feed_pour_tenant, generer_ics
from .job import PALIERS, Alerte, executer_job_alertes, scanner_alertes
from .mailer import Mailer, MailerMemoire, MailerSMTP

__all__ = [
    "PALIERS",
    "Alerte",
    "scanner_alertes",
    "executer_job_alertes",
    "Mailer",
    "MailerMemoire",
    "MailerSMTP",
    "EvenementCalendrier",
    "generer_ics",
    "feed_pour_tenant",
    "creer_token",
    "resoudre_token",
    "revoquer",
    "roter",
]
