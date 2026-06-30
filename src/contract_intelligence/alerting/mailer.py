"""Abstraction d'envoi de mail : SMTP (Mailpit en dev, Mailjet en prod) + mémoire (tests)."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol


class Mailer(Protocol):
    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None: ...


@dataclass
class MailerMemoire:
    """Mailer de test : conserve les messages en mémoire."""

    envoyes: list[tuple[str, str, str]] = field(default_factory=list)

    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        self.envoyes.append((destinataire, sujet, corps))


@dataclass
class MailerSMTP:
    """Mailer SMTP (Mailpit `localhost:1025` en dev)."""

    hote: str = "localhost"
    port: int = 1025
    expediteur: str = "clm@example.test"

    def envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        message = EmailMessage()
        message["From"] = self.expediteur
        message["To"] = destinataire
        message["Subject"] = sujet
        message.set_content(corps)
        with smtplib.SMTP(self.hote, self.port) as smtp:
            smtp.send_message(message)
