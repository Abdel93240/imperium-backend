"""vector: relevé complet dès qu'une session démarre ou reprend (2026-10-24)

Job `vector.session_kickoff` (abonné à `rides.session.started` et `rides.session.resumed`) : météo, perturbations,
trafic et avions relevés aussitôt. Sans lui, la carte Météo restait « ancienne » jusqu'à 30 min après le démarrage.
Allumé si le relevé météo l'est déjà.

Revision ID: 20261024_0146
Revises: 20261023_0145
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261024_0146"
down_revision: str | None = "20261023_0145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'vector.session_kickoff', 'event_subscription', NULL, "
        "ARRAY['rides.session.started', 'rides.session.resumed'], 'app.services.vector.feeds:session_kickoff_job', "
        "COALESCE((SELECT enabled FROM job_definitions WHERE code = 'vector.weather_refresh'), false), true, 300) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = 'vector.session_kickoff'")
