"""vector: relevés météo Open-Meteo pour l'apprentissage et le tableau de bord (2026-10-23)

`rides_weather_readings` : relevés Open-Meteo (modèle Météo-France, doc 33 §3) du centre de Paris, gardés 7 jours ;
chaque offre lit le relevé de son heure (doc 57 §5.5). Job `vector.weather_refresh` (toutes les 15 min), semé éteint.

Revision ID: 20261023_0139
Revises: 20261022_0138
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0139"
down_revision: str | None = "20261022_0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rides_weather_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Numeric(8, 5), nullable=False),
        sa.Column("longitude", sa.Numeric(8, 5), nullable=False),
        sa.Column("current", postgresql.JSONB(), nullable=False),
        sa.Column("hourly", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="open-meteo"),
    )
    op.create_index("rides_weather_readings_fetched_idx", "rides_weather_readings", [sa.text("fetched_at DESC")])
    op.get_bind().exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'vector.weather_refresh', 'cron', '*/15 * * * *', NULL, "
        "'app.services.vector.weather:weather_refresh_job', false, true, 60) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = 'vector.weather_refresh'")
    op.drop_index("rides_weather_readings_fetched_idx", table_name="rides_weather_readings")
    op.drop_table("rides_weather_readings")
