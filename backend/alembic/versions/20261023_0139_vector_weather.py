"""vector: météo en grille (Open-Meteo, Météo-France), relevée pendant les sessions VTC (2026-10-23)

`rides_weather_cell_readings` : une ligne par case et par passe — Paris et petite couronne en cases de ~3 km, reste
de l'Île-de-France ~10 km, aéroports — avec la pluie au quart d'heure. Gardées : données d'apprentissage de la
note des courses et de la prédiction de majoration (doc 57 §5.5, §17). Job `vector.weather_refresh` (toutes les
30 min, seulement si une session VTC est ouverte), semé éteint.

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
        "rides_weather_cell_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cell_code", sa.Text(), nullable=False),
        sa.Column("ring", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(8, 5), nullable=False),
        sa.Column("longitude", sa.Numeric(8, 5), nullable=False),
        sa.Column("current", postgresql.JSONB(), nullable=False),
        sa.Column("minutely", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("ring IN ('A', 'B', 'airport')", name="ring_check"),
    )
    op.create_index("rides_weather_cell_readings_fetched_idx", "rides_weather_cell_readings", [sa.text("fetched_at DESC")])
    op.create_index("rides_weather_cell_readings_cell_idx", "rides_weather_cell_readings",
                    ["cell_code", sa.text("fetched_at DESC")])
    op.get_bind().exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'vector.weather_refresh', 'cron', '*/30 * * * *', NULL, "
        "'app.services.vector.weather:weather_refresh_job', false, true, 120) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = 'vector.weather_refresh'")
    op.drop_index("rides_weather_cell_readings_cell_idx", table_name="rides_weather_cell_readings")
    op.drop_index("rides_weather_cell_readings_fetched_idx", table_name="rides_weather_cell_readings")
    op.drop_table("rides_weather_cell_readings")
