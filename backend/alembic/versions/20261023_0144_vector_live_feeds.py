"""vector: flux en temps réel — perturbations IDFM, trafic TomTom, avions OpenSky (2026-10-23)

Relevés pendant les sessions VTC seulement, gardés comme données d'apprentissage :
- `rides_transit_disruptions` : perturbations en cours des métros, RER, Transilien, trams (IDFM PRIM), avec les
  zones des arrêts touchés ; `rides_transit_stops` garde la position de chaque arrêt (demandée une fois) ;
- `rides_traffic_incidents` : bouchons, fermetures, travaux (TomTom), placés dans la grille ;
- `rides_airport_snapshots` : avions en approche finale et au sol à Roissy-CDG, Orly, Beauvais (OpenSky).
`rides_drop_observations.context` : la situation (pluie, perturbations, bouchons, avions) au lieu et à l'heure de
la dépose. Jobs `vector.transit_traffic_refresh` (10 min) et `vector.airports_refresh` (5 min), semés éteints.

Revision ID: 20261023_0144
Revises: 20261023_0143
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0144"
down_revision: str | None = "20261023_0143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS = [
    ("vector.transit_traffic_refresh", "*/10 * * * *", "app.services.vector.feeds:transit_traffic_job", 300),
    ("vector.airports_refresh", "*/5 * * * *", "app.services.vector.feeds:airports_job", 120),
]


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table(
        "rides_transit_stops",
        sa.Column("stop_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("zone_code", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rides_transit_disruptions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disruption_id", sa.Text(), nullable=False),
        sa.Column("line_id", sa.Text(), nullable=False),
        sa.Column("line_name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_ids", jsonb, nullable=False),
        sa.Column("zone_codes", jsonb, nullable=False),
    )
    op.create_index("rides_transit_disruptions_fetched_idx", "rides_transit_disruptions", [sa.text("fetched_at DESC")])
    op.create_table(
        "rides_traffic_incidents",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.Integer(), nullable=True),
        sa.Column("magnitude", sa.Integer(), nullable=True),
        sa.Column("delay_s", sa.Integer(), nullable=True),
        sa.Column("length_m", sa.Integer(), nullable=True),
        sa.Column("roads", jsonb, nullable=False),
        sa.Column("from_text", sa.Text(), nullable=True),
        sa.Column("to_text", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("zone_code", sa.Text(), nullable=False),
    )
    op.create_index("rides_traffic_incidents_fetched_idx", "rides_traffic_incidents", [sa.text("fetched_at DESC")])
    op.create_table(
        "rides_airport_snapshots",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("airport", sa.Text(), nullable=False),
        sa.Column("approaching", sa.Integer(), nullable=False),
        sa.Column("on_ground", sa.Integer(), nullable=False),
        sa.Column("final_icao", jsonb, nullable=False),
    )
    op.create_index("rides_airport_snapshots_idx", "rides_airport_snapshots", ["airport", sa.text("fetched_at DESC")])
    op.add_column("rides_drop_observations", sa.Column("context", jsonb, nullable=True))
    conn = op.get_bind()
    for code, schedule, handler, timeout in JOBS:
        conn.exec_driver_sql(
            "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
            "VALUES (gen_random_uuid(), %s, 'cron', %s, NULL, %s, false, true, %s) "
            "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING", (code, schedule, handler, timeout))


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = ANY(%s)", ([j[0] for j in JOBS],))
    op.drop_column("rides_drop_observations", "context")
    op.drop_index("rides_airport_snapshots_idx", table_name="rides_airport_snapshots")
    op.drop_table("rides_airport_snapshots")
    op.drop_index("rides_traffic_incidents_fetched_idx", table_name="rides_traffic_incidents")
    op.drop_table("rides_traffic_incidents")
    op.drop_index("rides_transit_disruptions_fetched_idx", table_name="rides_transit_disruptions")
    op.drop_table("rides_transit_disruptions")
    op.drop_table("rides_transit_stops")
