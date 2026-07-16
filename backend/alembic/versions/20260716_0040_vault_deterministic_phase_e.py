"""vault deterministic phase e: pressure, upcoming expenses, weekly summaries

Revision ID: 20260716_0040
Revises: 20260715_0039
Create Date: 2026-07-16

Phase E creates the deterministic Vault foundation and removes the orphaned
legacy vault_transactions table after pg_dump archive
backend/db_archives/20260716_vault_transactions_pre_drop.pg_dump.sql.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20260716_0040"
down_revision: str | None = "20260715_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRESSURE_BANDS = [
    {"label": "safe", "min": 0, "max": 20},
    {"label": "stable", "min": 21, "max": 40},
    {"label": "attention", "min": 41, "max": 60},
    {"label": "pressure", "min": 61, "max": 80},
    {"label": "critical", "min": 81, "max": 100},
]

PARAMETERS = [
    (
        "vault.pressure_thresholds",
        "vault",
        PRESSURE_BANDS,
        "score",
        "Bornes canoniques doc 11, échelle Q4 0-100.",
    ),
    (
        "vault.category_map",
        "vault",
        {
            "business_income": ["vtc", "bolt", "uber", "heetch", "autre pro", "other_professional"],
            "personal_income": ["rsa", "gift", "salaire", "side income", "leboncoin"],
            "business_expenses": [
                "fuel",
                "carburant",
                "plateformes",
                "entretien",
                "maintenance",
                "assurance pro",
                "outils vtc",
                "charges",
                "urssaf",
                "tax",
                "provision impôt",
            ],
            "personal_expenses": [
                "courses",
                "loyer",
                "restaurant",
                "loisirs",
                "vêtements",
                "telephone",
                "téléphone",
                "santé",
                "abonnements",
                "sadaqa",
            ],
        },
        None,
        "Mapping déterministe business/personnel Vault V1, à valider par usage.",
    ),
    ("vault.horizon_days", "vault", 45, "days", "Horizon pression doc 11 / Phase E."),
]

JOB_DEFINITIONS = [
    (
        "vault.weekly_profit",
        "cron",
        "30 0 * * 1",
        None,
        "app.services.vault.weekly:weekly_profit_job",
        300,
    ),
    (
        "vault.pressure_refresh",
        "event_subscription",
        "0 6 * * *",
        ["finance.transaction.*"],
        "app.services.vault.pressure:pressure_refresh_job",
        300,
    ),
    (
        "vault.expenses_horizon",
        "cron",
        "0 6 * * *",
        None,
        "app.services.vault.upcoming:expenses_horizon_job",
        300,
    ),
]


def upgrade() -> None:
    op.create_table(
        "upcoming_expenses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("label_fr", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("recurrence", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="upcoming_expenses_amount_positive"),
        sa.CheckConstraint(
            "recurrence IS NULL OR recurrence IN ('monthly', 'quarterly', 'yearly')",
            name="upcoming_expenses_recurrence_check",
        ),
    )
    op.create_index("upcoming_expenses_due_active_idx", "upcoming_expenses", ["active", "due_date"])
    op.create_index("upcoming_expenses_category_idx", "upcoming_expenses", ["category"])

    op.create_table(
        "weekly_finance_summaries",
        sa.Column("week_start", sa.Date(), primary_key=True),
        sa.Column("business_revenue", sa.Numeric(12, 2), nullable=False),
        sa.Column("business_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("weekly_business_profit", sa.Numeric(12, 2), nullable=False),
        sa.Column("personal_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", JSONB(), nullable=False),
    )

    op.create_table(
        "pressure_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("factors", JSONB(), nullable=False),
        sa.Column("daily_targets", JSONB(), nullable=False),
        sa.Column("inputs_snapshot", JSONB(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="pressure_snapshots_score_range"),
        sa.CheckConstraint(
            "label IN ('safe', 'stable', 'attention', 'pressure', 'critical')",
            name="pressure_snapshots_label_check",
        ),
    )
    op.create_index("pressure_snapshots_computed_at_idx", "pressure_snapshots", [sa.text("computed_at DESC")])
    op.execute(
        """
        CREATE FUNCTION pressure_snapshots_append_only_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'pressure_snapshots is append-only: rows are never updated';
          END IF;
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'pressure_snapshots is append-only: rows are never deleted';
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER pressure_snapshots_append_only_guard
        BEFORE UPDATE OR DELETE ON pressure_snapshots
        FOR EACH ROW EXECUTE FUNCTION pressure_snapshots_append_only_guard();
        """
    )
    op.execute(
        """
        CREATE TRIGGER pressure_snapshots_append_only_truncate_guard
        BEFORE TRUNCATE ON pressure_snapshots
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_append_only_truncate();
        """
    )

    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )

    conn.exec_driver_sql(
        """
        INSERT INTO signal_definitions
          (id, domain, code, label_fr, unit, source, aggregation, baseline_window_days,
           bands, staleness_hours, active, version)
        VALUES
          (gen_random_uuid(), 'vault', 'vault.pressure', 'Pression financière Vault',
           'score_0_100', 'pressure_snapshots', 'latest', NULL, %s::jsonb, 24, true, 1)
        ON CONFLICT ON CONSTRAINT signal_definitions_code_unique DO NOTHING
        """,
        (json.dumps({"baseline_method": "none", "bands": PRESSURE_BANDS}),),
    )

    for code, kind, schedule, event_types, handler_ref, timeout_s in JOB_DEFINITIONS:
        conn.exec_driver_sql(
            """
            INSERT INTO job_definitions
              (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, false, true, %s)
            ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
            """,
            (code, kind, schedule, event_types, handler_ref, timeout_s),
        )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_user') THEN
            GRANT SELECT, INSERT, UPDATE ON upcoming_expenses TO imperium_user;
            GRANT SELECT, INSERT, UPDATE ON weekly_finance_summaries TO imperium_user;
            GRANT SELECT, INSERT ON pressure_snapshots TO imperium_user;
          END IF;
        END $$;
        """
    )

    op.drop_table("vault_transactions")


def downgrade() -> None:
    conn = op.get_bind()
    job_codes = [job[0] for job in JOB_DEFINITIONS]
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = ANY(%s)", (job_codes,))
    conn.exec_driver_sql("DELETE FROM signal_values WHERE signal_code = 'vault.pressure'")
    conn.exec_driver_sql("DELETE FROM signal_definitions WHERE code = 'vault.pressure'")
    param_codes = [parameter[0] for parameter in PARAMETERS]
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql(
            "DELETE FROM parameters WHERE code = ANY(%s) AND version = 1 AND origin = 'seed'",
            (param_codes,),
        )
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")

    op.create_table(
        "vault_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_app", sa.Text(), nullable=False, server_default="vault"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense', 'correction')",
            name="vault_transactions_transaction_type_check",
        ),
        sa.CheckConstraint("wallet IN ('cash', 'bank')", name="vault_transactions_wallet_check"),
        sa.CheckConstraint("amount > 0", name="vault_transactions_amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="vault_transactions_user_id_fkey"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="vault_transactions_event_id_fkey"),
    )
    op.create_index("vault_transactions_user_local_date_idx", "vault_transactions", ["user_id", "local_date"])
    op.create_index("vault_transactions_user_occurred_at_idx", "vault_transactions", ["user_id", sa.text("occurred_at DESC")])
    op.create_index("vault_transactions_user_transaction_type_idx", "vault_transactions", ["user_id", "transaction_type"])

    op.execute("DROP TRIGGER IF EXISTS pressure_snapshots_append_only_truncate_guard ON pressure_snapshots")
    op.execute("DROP TRIGGER IF EXISTS pressure_snapshots_append_only_guard ON pressure_snapshots")
    op.execute("DROP FUNCTION IF EXISTS pressure_snapshots_append_only_guard()")
    op.drop_index("pressure_snapshots_computed_at_idx", table_name="pressure_snapshots")
    op.drop_table("pressure_snapshots")
    op.drop_table("weekly_finance_summaries")
    op.drop_index("upcoming_expenses_category_idx", table_name="upcoming_expenses")
    op.drop_index("upcoming_expenses_due_active_idx", table_name="upcoming_expenses")
    op.drop_table("upcoming_expenses")
