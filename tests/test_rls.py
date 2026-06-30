"""Tests RLS multi-tenant + audit append-only (PostgreSQL).

Nécessite un PostgreSQL via `CI_TEST_DATABASE_URL` (connexion superuser pour
appliquer les migrations et créer un rôle applicatif). Les assertions d'isolation
utilisent un rôle **non-superuser** `clm_app` car la RLS `FORCE` ne s'applique pas
aux superusers. Skippé hors CI.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from contract_intelligence.db import Contrat, EvenementAudit, make_sessionmaker, tenant_session

DB_URL = os.environ.get("CI_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DB_URL, reason="CI_TEST_DATABASE_URL requis (PostgreSQL)"),
]


@pytest.fixture(scope="module")
def app_factory():
    from alembic import command
    from alembic.config import Config

    assert DB_URL is not None
    admin = create_engine(DB_URL, future=True)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    command.upgrade(cfg, "head")

    # Rôle applicatif non-superuser (soumis à la RLS FORCE).
    with admin.begin() as c:
        c.execute(
            text(
                "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='clm_app') "
                "THEN CREATE ROLE clm_app LOGIN PASSWORD 'app' NOSUPERUSER; END IF; END $$"
            )
        )
        c.execute(text("GRANT USAGE ON SCHEMA public TO clm_app"))
        c.execute(
            text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO clm_app")
        )
        c.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO clm_app"))

    app_url = make_url(DB_URL).set(username="clm_app", password="app")
    app_engine = create_engine(app_url, future=True)
    return make_sessionmaker(app_engine)


def test_rls_activee_et_forcee():
    assert DB_URL is not None
    admin = create_engine(DB_URL, future=True)
    with admin.connect() as c:
        rows = c.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN ('document', 'contrat', 'evenement_audit')"
            )
        ).all()
    assert rows and all(r.relrowsecurity and r.relforcerowsecurity for r in rows)


def test_isolation_entre_tenants(app_factory):
    cid = uuid.uuid4()
    with tenant_session(app_factory, "acme") as s:
        s.add(Contrat(id=cid, tenant="acme", objet="bail acme"))

    with tenant_session(app_factory, "acme") as s:
        assert s.get(Contrat, cid) is not None

    with tenant_session(app_factory, "globex") as s:
        assert s.get(Contrat, cid) is None
        assert s.execute(select(Contrat).where(Contrat.id == cid)).first() is None


def test_audit_append_only(app_factory):
    with tenant_session(app_factory, "acme") as s:
        ev = EvenementAudit(tenant="acme", type_evenement="TEST")
        s.add(ev)
        s.flush()
        eid = ev.id

    with pytest.raises(Exception):  # noqa: B017 — le trigger lève une exception DB
        with tenant_session(app_factory, "acme") as s:
            s.execute(
                text("UPDATE evenement_audit SET type_evenement='X' WHERE id=:i"),
                {"i": str(eid)},
            )
