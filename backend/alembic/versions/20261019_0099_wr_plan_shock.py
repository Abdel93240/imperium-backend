"""wr plan shock: shock taxonomy and the manual shock regeneration switch (spec WR §8.1, §13.6, ACT-WR-20)

Paramètres `wr.shock_taxonomy` (seed spec §13.6, éditable, À VALIDER) et `wr.plan_shock_enabled`
= false (route `POST /api/wr/plan/shock` coupée). Déclenchement MANUEL seulement : aucun abonnement
aux replans ordinaires. Tant que `real_ai_enabled` est faux, la régénération est un essai à blanc
(copie du plan courant, `model_used=dry_run`), toujours `proposed`, jamais activée seule. Pas de DDL.

Revision ID: 20261019_0099
Revises: 20261019_0098
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0099"
down_revision: str | None = "20261019_0098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHOCK_TAXONOMY = [
    {"code": "vehicle_accident", "label_fr": "Accident du véhicule"},
    {"code": "immobilizing_breakdown", "label_fr": "Panne immobilisante"},
    {"code": "major_family_event", "label_fr": "Événement familial majeur"},
    {"code": "income_source_loss", "label_fr": "Perte d'une source de revenu"},
    {"code": "disabling_injury", "label_fr": "Blessure invalidante"},
    {"code": "housing_disaster", "label_fr": "Sinistre du logement"},
]
PARAMETERS = [
    ("wr.shock_taxonomy", SHOCK_TAXONOMY, "json",
     "Raisons de choc exogène qui ouvrent une régénération complète du plan (spec WR §8.1, §13.6, À VALIDER)."),
    ("wr.plan_shock_enabled", False, "bool",
     "Route de régénération choc POST /api/wr/plan/shock (carte ACT-WR-20). Coupée au seed."),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, 'wr', %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, json.dumps(value), unit, rationale),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
