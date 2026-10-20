"""daily prayers as fixed commitments in G4 with mosque choice (Q6 tranchée ; ACT-DLY-10 ; doc 41 §6, §7-bis)

1. `path_registered_mosques.adhan_offsets` / `iqama_offsets` (jsonb {prière: minutes}) : décalage saisi de
   l'adhan d'une mosquée par rapport au calcul local à ses coordonnées, et attente adhan → iqama. Servent
   tant que MAWAQIT n'est pas autorisé pour toutes les mosquées (le cache MAWAQIT passe devant s'il existe).
2. `daily_selection_log.next_fixed_kind` accepte `prayer`.
3. Paramètres : `daily.prayer_commitments_enabled` false ; rayon en minutes de trajet, marge sur le trajet,
   bloc après l'iqama, bloc de prière seul, attente par défaut adhan → iqama.

Revision ID: 20261020_0113
Revises: 20261020_0112
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0113"
down_revision: str | None = "20261020_0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("daily.prayer_commitments_enabled", "daily", False, "bool",
     "La porte G4 s'arrête au départ vers la prière suivante (Q6, carte ACT-DLY-10)."),
    ("path.mosque_search_travel_min", "path", 20, "min",
     "Mosquées candidates : trajet estimé (marge comprise) au plus de tant de minutes (décision utilisateur)."),
    ("path.mosque_travel_margin_pct", "path", 20, "%",
     "Marge ajoutée au temps de trajet vers la mosquée (décision utilisateur)."),
    ("path.prayer_after_iqama_min", "path", 15, "min",
     "Bloc de prière : jusqu'à tant de minutes après l'iqama de la mosquée (décision utilisateur)."),
    ("path.prayer_solo_block_min", "path", 20, "min",
     "Bloc de prière quand aucune mosquée n'est joignable, ou sans iqama connue : à partir de l'adhan."),
]


def upgrade() -> None:
    op.add_column("path_registered_mosques", sa.Column("adhan_offsets", postgresql.JSONB(), nullable=False,
                                                       server_default=sa.text("'{}'::jsonb")))
    op.add_column("path_registered_mosques", sa.Column("iqama_offsets", postgresql.JSONB(), nullable=False,
                                                       server_default=sa.text("'{}'::jsonb")))
    op.drop_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log",
                               "next_fixed_kind IS NULL OR next_fixed_kind IN ('mission', 'calendar_event', 'prayer')")
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


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("UPDATE daily_selection_log SET next_fixed_kind = NULL, next_fixed_ref = NULL "
               "WHERE next_fixed_kind = 'prayer'")
    op.drop_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log",
                               "next_fixed_kind IS NULL OR next_fixed_kind IN ('mission', 'calendar_event')")
    op.drop_column("path_registered_mosques", "iqama_offsets")
    op.drop_column("path_registered_mosques", "adhan_offsets")
