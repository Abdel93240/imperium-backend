"""vector: vacances scolaires et scan hebdomadaire des événements et fermetures (2026-10-23)

- `rides_school_holidays` : calendrier scolaire de la zone C (Paris), open data de l'Éducation nationale ; job
  `vector.school_holidays_refresh` (lundi 03:30), semé éteint. Variable `is_school_holiday` des offres.
- `rides_event_scans` et `rides_event_signals` : scan web hebdomadaire `vector.event_scan` (doc 31 §10, lundi 03:00)
  par le spécialiste web (rôle `web_fresh_data`, recherche web permise pour ce seul slot) : événements (concert, sport,
  salon, spectacle…), fermetures routières et travaux (Sytadin sans API), travaux sur le rail. Signal passif, sans
  validation (doc 31 §10) ; il nourrit les variables des offres et la carte Événements. Slot et job semés éteints.

Revision ID: 20261023_0140
Revises: 20261023_0139
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0140"
down_revision: str | None = "20261023_0139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS = [
    ("vector.school_holidays_refresh", "30 3 * * 1", "app.services.vector.school:school_holidays_job", 120),
    ("vector.event_scan", "0 3 * * 1", "app.services.vector.events:event_scan_job", 1800),
]


def upgrade() -> None:
    op.create_table(
        "rides_school_holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("zone", sa.Text(), nullable=False),
        sa.Column("school_year", sa.Text(), nullable=False),
        sa.Column("start_day", sa.Date(), nullable=False),
        sa.Column("end_day", sa.Date(), nullable=False),  # jour de reprise, exclu
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("zone", "label", "start_day", name="period_unique"),
        sa.CheckConstraint("end_day >= start_day", name="period_order"),
    )
    op.create_table(
        "rides_event_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('running', 'done', 'failed')", name="status_check"),
    )
    op.create_table(
        "rides_event_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides_event_scans.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column("commune", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("road", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_attendance", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('event', 'road_closure', 'rail_works')", name="kind_check"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="period_order"),
        sa.UniqueConstraint("fingerprint", name="fingerprint_unique"),
    )
    op.create_index("rides_event_signals_window_idx", "rides_event_signals", ["starts_at", "ends_at"])
    conn = op.get_bind()
    conn.exec_driver_sql(
        "INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr) "
        "VALUES (gen_random_uuid(), 'vector.event_scan', 'vector', 'cloud_forced', 100, 92, "
        "'Scan web hebdomadaire des événements, fermetures routières et travaux en Île-de-France (recherche web "
        "permise pour ce seul slot), à activer par l''utilisateur.') "
        "ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING")
    for code, schedule, handler, timeout in JOBS:
        conn.exec_driver_sql(
            "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
            "VALUES (gen_random_uuid(), %s, 'cron', %s, NULL, %s, false, true, %s) "
            "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING", (code, schedule, handler, timeout))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = ANY(%s)", ([j[0] for j in JOBS],))
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = 'vector.event_scan'")
    op.drop_index("rides_event_signals_window_idx", table_name="rides_event_signals")
    op.drop_table("rides_event_signals")
    op.drop_table("rides_event_scans")
    op.drop_table("rides_school_holidays")
