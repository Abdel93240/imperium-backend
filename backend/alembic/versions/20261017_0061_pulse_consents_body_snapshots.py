"""pulse health consents + body snapshots (cadre santé sensible, doc 40 §14, doc 05)

Cadre validé par l'utilisateur le 2026-10-17 :
- consentement explicite par domaine (body, pain, medical), daté, retirable ; sans
  consentement actif, les écritures du domaine sont refusées ;
- aucune photo côté serveur (la table n'a pas de colonne pour elle) ;
- suppression réelle à la demande ; les événements ne portent aucune mesure.

Revision ID: 20261017_0061
Revises: 20261017_0060
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0061"
down_revision: str | None = "20261017_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pulse_health_consents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("text_version", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("domain IN ('body', 'pain', 'medical')", name="domain_check"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="revoked_after_granted"),
    )
    op.create_index(
        "pulse_health_consents_user_domain_active_idx", "pulse_health_consents", ["user_id", "domain"], unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "pulse_body_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("body_fat_percent", sa.Numeric(4, 2), nullable=True),
        sa.Column("waist_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("chest_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("arm_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "weight_kg IS NOT NULL OR body_fat_percent IS NOT NULL OR waist_cm IS NOT NULL OR chest_cm IS NOT NULL "
            "OR arm_cm IS NOT NULL",
            name="one_measure",
        ),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="weight_positive"),
        sa.CheckConstraint("body_fat_percent IS NULL OR body_fat_percent BETWEEN 1 AND 70", name="body_fat_range"),
    )
    op.create_index("pulse_body_snapshots_user_measured_idx", "pulse_body_snapshots", ["user_id", "measured_at"])
    op.create_index(
        "pulse_body_snapshots_user_idempotency_idx", "pulse_body_snapshots", ["user_id", "idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("pulse_body_snapshots_user_idempotency_idx", table_name="pulse_body_snapshots")
    op.drop_index("pulse_body_snapshots_user_measured_idx", table_name="pulse_body_snapshots")
    op.drop_table("pulse_body_snapshots")
    op.drop_index("pulse_health_consents_user_domain_active_idx", table_name="pulse_health_consents")
    op.drop_table("pulse_health_consents")
