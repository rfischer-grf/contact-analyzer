"""Tests de génération ICS + feed par tenant (§2.6)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine

from contract_intelligence.alerting import (
    EvenementCalendrier,
    feed_pour_tenant,
    generer_ics,
)
from contract_intelligence.db import Base, Contrat, make_sessionmaker


def test_generer_ics_sans_valarm() -> None:
    ics = generer_ics(
        [
            EvenementCalendrier("c1-echeance", date(2025, 12, 31), "Échéance — C-1"),
            EvenementCalendrier("c1-denonciation", date(2025, 9, 30), "Date limite — C-1"),
        ]
    )
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20251231" in ics
    assert "SUMMARY:Échéance — C-1" in ics
    # Garde-fou §7 : pas de VALARM dans le feed.
    assert "VALARM" not in ics
    assert ics.endswith("END:VCALENDAR\r\n")


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def test_feed_pour_tenant(factory) -> None:
    with factory() as s:
        s.add(
            Contrat(
                id=uuid.uuid4(),
                tenant="acme",
                reference="C-1",
                date_echeance=date(2025, 12, 31),
                date_limite_denonciation=date(2025, 9, 30),
            )
        )
        s.add(
            Contrat(
                id=uuid.uuid4(), tenant="globex", reference="G-1", date_echeance=date(2026, 1, 1)
            )
        )
        s.commit()

    with factory() as s:
        evs = feed_pour_tenant(s, "acme")
    # Un seul contrat acme → échéance + date limite = 2 évènements, rien de globex.
    assert len(evs) == 2
    assert all("C-1" in e.intitule for e in evs)
