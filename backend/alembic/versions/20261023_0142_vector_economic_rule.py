"""vector: règle économique (€/h global et note de la zone d'arrivée) et notes de zone modifiables (2026-10-23)

Décision utilisateur : vert si le €/h global (prix ÷ approche + course) atteint 25 €/h, rouge en dessous ; une zone
d'arrivée excellente au moment où la course finit rend vert ; une zone mauvaise ajoute le temps de repositionnement
vers une zone correcte avant de calculer. `rides_zone_scores` : notes posées par l'utilisateur (sinon valeurs par
défaut du code), par code postal ou département, par créneau. Paramètre `vector.economic_rule`.

Revision ID: 20261023_0142
Revises: 20261023_0141
Create Date: 2026-10-23
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_0142"
down_revision: str | None = "20261023_0141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE = {"min_hourly_eur": 25, "excellent_zone": 8, "bad_zone": 4, "good_zone": 6, "reposition_speed_kmh": 30,
        "reposition_extra_min": 5}


def upgrade() -> None:
    op.create_table(
        "rides_zone_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_key", sa.Text(), nullable=False),  # code postal (75011) ou département (93)
        sa.Column("time_block", sa.Text(), nullable=False),  # night | morning | daytime | evening | late_evening | all
        sa.Column("score", sa.Numeric(3, 1), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("score BETWEEN 0 AND 10", name="score_range"),
        sa.CheckConstraint("time_block IN ('night', 'morning', 'daytime', 'evening', 'late_evening', 'all')",
                           name="time_block_check"),
        sa.UniqueConstraint("zone_key", "time_block", name="zone_block_unique"),
    )
    op.get_bind().exec_driver_sql(
        "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
        "VALUES (gen_random_uuid(), 'vector.economic_rule', 'vector', %s::jsonb, NULL, %s, 'seed', 1) "
        "ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING",
        (json.dumps(RULE), "Règle économique de Vector : seuil de €/h global, notes de zone excellente / correcte / "
                           "mauvaise, vitesse et marge du repositionnement (décision utilisateur 2026-10-23)."))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = 'vector.economic_rule'")
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_table("rides_zone_scores")
