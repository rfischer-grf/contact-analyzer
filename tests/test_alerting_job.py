"""Tests du job d'alerte quotidien (§2.6) sur SQLite."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select

from contract_intelligence.alerting import MailerMemoire, executer_job_alertes, scanner_alertes
from contract_intelligence.db import Base, Contrat, EvenementAudit, make_sessionmaker

AUJOURD_HUI = date(2026, 1, 1)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    f = make_sessionmaker(engine)
    with f() as s:
        # Paliers : J-90 et J-30 alertables ; J-45 non ; date limite absente ignorée.
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                date_limite_denonciation=AUJOURD_HUI + timedelta(days=90),
            )
        )
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                date_limite_denonciation=AUJOURD_HUI + timedelta(days=30),
            )
        )
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="globex",
                date_limite_denonciation=AUJOURD_HUI + timedelta(days=45),
            )
        )
        s.add(Contrat(id=uuid.uuid4(), tenant="acme", date_limite_denonciation=None))
        s.commit()
    return f


def test_scanner_alertes(factory) -> None:
    with factory() as s:
        alertes = scanner_alertes(s, AUJOURD_HUI)
    paliers = sorted(a.jours_restants for a in alertes)
    assert paliers == [30, 90]


def test_executer_job_envoie_et_logue(factory) -> None:
    mailer = MailerMemoire()
    with factory() as s:
        alertes = executer_job_alertes(s, AUJOURD_HUI, mailer)
        s.commit()
    assert len(alertes) == 2
    assert len(mailer.envoyes) == 2
    with factory() as s:
        logs = (
            s.execute(
                select(EvenementAudit).where(EvenementAudit.type_evenement == "ALERTE_ENVOYEE")
            )
            .scalars()
            .all()
        )
    assert len(logs) == 2
