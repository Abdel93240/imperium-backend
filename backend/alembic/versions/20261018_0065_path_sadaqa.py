"""path sadaqa: settings, donations, closed weeks (doc 41 §9)

Réglages : une ligne par changement (pourcentage 1–20 %, marge 10–15 %), valable à partir
d'un lundi. Dons déclarés par l'utilisateur, puis dépense « sadaqa » écrite au Vault
(statut pending tant que l'écriture n'a pas réussi). Semaines closes : cible, dons et reste
figés, base du report. Job `path.sadaqa_week_close` (semé désactivé) le lundi après le
bénéfice hebdomadaire du Vault.

Revision ID: 20261018_0065
Revises: 20261018_0064
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0065"
down_revision: str | None = "20261018_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JOB_CODE = "path.sadaqa_week_close"
HANDLER_REF = "app.services.path.sadaqa:sadaqa_week_close_job"


def upgrade() -> None:
    op.create_table(
        "path_sadaqa_settings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 4), nullable=False),
        sa.Column("safety_margin", sa.Numeric(5, 4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("percentage BETWEEN 0.01 AND 0.20", name="percentage_range"),
        sa.CheckConstraint("safety_margin BETWEEN 0.10 AND 0.15", name="safety_margin_range"),
        sa.CheckConstraint("extract(isodow from effective_from) = 1", name="effective_from_monday"),
    )
    op.create_index(
        "path_sadaqa_settings_user_effective_idx", "path_sadaqa_settings", ["user_id", "effective_from", "created_at"]
    )
    op.create_table(
        "path_sadaqa_donations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("donated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("related_week_start", sa.Date(), nullable=False),
        sa.Column("allocation", postgresql.JSONB(), nullable=False),
        sa.Column("record_in_vault", sa.Boolean(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("vault_status", sa.Text(), nullable=False),
        sa.Column("vault_transaction_id", UUID, nullable=True),  # sans FK : registre Vault en ajout seul
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_cents > 0 AND amount_cents <= 10000000", name="amount_range"),
        sa.CheckConstraint("extract(isodow from related_week_start) = 1", name="related_week_monday"),
        sa.CheckConstraint("vault_status IN ('not_requested', 'pending', 'recorded')", name="vault_status_check"),
        sa.CheckConstraint("vault_status <> 'recorded' OR vault_transaction_id IS NOT NULL", name="recorded_has_transaction"),
    )
    op.create_index("path_sadaqa_donations_user_week_idx", "path_sadaqa_donations", ["user_id", "related_week_start"])
    op.create_index(
        "path_sadaqa_donations_user_idempotency_idx", "path_sadaqa_donations", ["user_id", "idempotency_key"], unique=True
    )
    op.create_table(
        "path_sadaqa_weeks",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("week_start", sa.Date(), primary_key=True),
        sa.Column("business_profit_cents", sa.Integer(), nullable=False),
        sa.Column("profit_source", sa.Text(), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 4), nullable=False),
        sa.Column("safety_margin", sa.Numeric(5, 4), nullable=False),
        sa.Column("base_target_cents", sa.Integer(), nullable=False),
        sa.Column("carried_in_cents", sa.Integer(), nullable=False),
        sa.Column("target_cents", sa.Integer(), nullable=False),
        sa.Column("donated_cents", sa.Integer(), nullable=False),
        sa.Column("remaining_cents", sa.Integer(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("extract(isodow from week_start) = 1", name="week_start_monday"),
        sa.CheckConstraint("remaining_cents >= 0", name="remaining_not_negative"),
    )
    # Lundi 01:00 UTC : après vault.weekly_profit (00:30 UTC), semaine de Paris close dans les deux saisons.
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), %s, 'cron', '0 1 * * 1', NULL, %s, false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """,
        (JOB_CODE, HANDLER_REF),
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = %s", (JOB_CODE,))
    op.drop_table("path_sadaqa_weeks")
    op.drop_index("path_sadaqa_donations_user_idempotency_idx", table_name="path_sadaqa_donations")
    op.drop_index("path_sadaqa_donations_user_week_idx", table_name="path_sadaqa_donations")
    op.drop_table("path_sadaqa_donations")
    op.drop_index("path_sadaqa_settings_user_effective_idx", table_name="path_sadaqa_settings")
    op.drop_table("path_sadaqa_settings")
