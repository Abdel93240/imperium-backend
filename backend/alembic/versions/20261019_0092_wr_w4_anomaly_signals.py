"""wr W4 anomalies: rollup signals in the shared signal_definitions, docket threshold (spec WR §4 W4, W5)

Signaux `wr.*` semés INACTIFS dans la table partagée `signal_definitions` (doc 78 F2-13 : jamais de
table wr_). Bandes = écart à la médiane glissante 28 j en MAD normalisés (yellow 2, orange 3, red 4),
dans le sens qui inquiète ; `min_scale` évite qu'une historique plate (MAD 0) crie au moindre écart.
`wr.anomaly_docket_min_band` : bande à partir de laquelle W5 dépose un item `anomaly` au docket.

Revision ID: 20261019_0092
Revises: 20261019_0091
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0092"
down_revision: str | None = "20261019_0091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BANDS = {"method": "median_mad", "yellow": 2, "orange": 3, "red": 4, "min_history_days": 14}

# (code, libellé, unité, métrique du rollup, sens, plancher d'échelle, ignorer les jours à zéro)
SIGNALS = [
    ("wr.finance.income", "Revenus du jour", "cents", "finance.income_cents", "low", 1000, False),
    ("wr.finance.expense", "Dépenses du jour", "cents", "finance.expense_cents", "high", 1000, False),
    ("wr.finance.pressure", "Score de pression", "score", "finance.pressure_score", "high", 5, False),
    ("wr.rides.net_per_hour", "Net VTC par heure", "cents", "rides.net_per_hour_cents", "low", 200, True),
    ("wr.rides.worked_minutes", "Minutes de conduite", "min", "rides.worked_minutes", "both", 30, True),
    ("wr.missions.failed", "Missions ratées", "count", "missions.failed", "high", 1, False),
    ("wr.missions.completed_late", "Missions finies en retard", "count", "missions.completed_late", "high", 1, False),
    ("wr.missions.overdue_open", "Missions ouvertes en retard", "count", "missions.overdue_open_at_day_end", "high", 1, False),
]

PARAMETERS = [
    ("wr.anomaly_docket_min_band", "wr", "orange", "band",
     "Bande à partir de laquelle une anomalie W4 devient un item du docket (yellow reste un signal, À VALIDER)."),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, label, unit, metric, direction, min_scale, skip_zero in SIGNALS:
        bands = {**_BANDS, "direction": direction, "min_scale": min_scale, "skip_zero": skip_zero}
        conn.exec_driver_sql(
            """
            INSERT INTO signal_definitions
              (id, domain, code, label_fr, unit, source, aggregation, baseline_window_days, bands, active)
            VALUES (gen_random_uuid(), 'wr', %s, %s, %s, %s, 'daily', 28, %s::jsonb, false)
            ON CONFLICT ON CONSTRAINT signal_definitions_code_unique DO NOTHING
            """,
            (code, label, unit, f"wr_rollups_daily:{metric}", json.dumps(bands)),
        )
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
    codes = [signal[0] for signal in SIGNALS]
    conn.exec_driver_sql("DELETE FROM signal_values WHERE signal_code = ANY(%s)", (codes,))
    conn.exec_driver_sql("DELETE FROM signal_definitions WHERE code = ANY(%s)", (codes,))
