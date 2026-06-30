"""Schéma initial + RLS multi-tenant + audit append-only.

Crée les tables depuis les métadonnées ORM, puis (PostgreSQL uniquement) active
la Row-Level Security `FORCE` + politiques d'isolation par tenant, et un trigger
rendant `evenement_audit` append-only.

Revision ID: 0001
Revises:
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import contract_intelligence.db.models  # noqa: F401 — enregistre les tables
from contract_intelligence.db.base import Base

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables porteuses de données tenant → soumises à la RLS.
RLS_TABLES = ("document", "contrat", "evenement_audit", "correction")


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    if bind.dialect.name != "postgresql":
        return  # RLS/trigger spécifiques PostgreSQL (les tests SQLite s'arrêtent ici)

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE : la RLS s'applique aussi au propriétaire de la table.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant = current_setting('app.current_tenant', true)) "
            "WITH CHECK (tenant = current_setting('app.current_tenant', true))"
        )

    # Piste d'audit append-only : refuse UPDATE/DELETE.
    op.execute(
        "CREATE OR REPLACE FUNCTION refuse_modif_audit() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'evenement_audit est append-only'; END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_append_only "
        "BEFORE UPDATE OR DELETE ON evenement_audit "
        "FOR EACH ROW EXECUTE FUNCTION refuse_modif_audit()"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_append_only ON evenement_audit")
        op.execute("DROP FUNCTION IF EXISTS refuse_modif_audit()")
        for table in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    Base.metadata.drop_all(bind=bind)
