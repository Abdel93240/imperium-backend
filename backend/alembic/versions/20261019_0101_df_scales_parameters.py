"""df scales parameters: Decision Framework scales externalised, seeded identical to the code (spec Daily §4, ACT-DLY-01)

Paramètres versionnés `df.*` (barèmes A-E, maxima par critère, coefficients par position,
seuils des buckets), semés DEPUIS les constantes du code (`decision_framework.CODE_SCALES`, valeurs
recopiées ici pour figer la migration) ; parité prouvée par tests dorés. `imperium_user_priorities`
reste la source de l'ORDRE des domaines. Pas de DDL.

Revision ID: 20261019_0101
Revises: 20261019_0100
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0101"
down_revision: str | None = "20261019_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = {
    "df.deadline_points": (
        {"overdue_or_today": 30, "bands": [[2, 25], [6, 20], [14, 15], [30, 10]], "beyond": 5},
        "Critère A (doc 52) : points selon les jours avant l'échéance ; bande [jours max, points], au-delà `beyond`."),
    "df.impact_points": (
        {"cosmetic": 0, "quality_of_life": 5, "quality-of-life": 5, "mid": 10, "paperwork": 10, "important": 15,
         "critical": 20, "vital_short_term": 25, "vital-short-term": 25, "vital_immediate": 30, "vital-immediate": 30},
        "Critère B (doc 52) : points par gravité de l'impact."),
    "df.mission_type_points": (
        {"cat_a": 20, "vital_immediate": 20, "cat_b": 18, "legal_contractual": 18, "cat_c": 15, "medical_planned": 15,
         "cat_d": 12, "religious_obligatory": 12, "cat_e": 10, "work_income": 10, "cat_f": 8, "learning": 8,
         "cat_g": 5, "health_routine": 5, "cat_h": 3, "quality_of_life": 3, "cat_i": 0, "optional": 0},
        "Critère C (doc 52) : points par catégorie de mission A-I (et leurs noms)."),
    "df.dependency_points": (
        {"labels": {"none": 0, "no": 0, "false": 0, "one_two": 5, "one-two": 5, "some": 5, "true": 5, "multiple": 10,
                    "many": 10},
         "bool_true": 5, "bool_false": 0, "blocked_count_bands": [[0, 0], [2, 5]], "blocked_count_beyond": 10},
        "Critère D (doc 52) : points de déblocage (libellé, booléen ou nombre de missions bloquées)."),
    "df.recurrence_points": (
        {"daily": 0, "quotidien": 0, "weekly": 3, "hebdomadaire": 3, "monthly": 5, "mensuel": 5, "yearly": 7,
         "annual": 7, "annuel": 7, "exceptional": 10, "unique": 10},
        "Critère E (doc 52) : points par rareté de la récurrence."),
    "df.criterion_max": (
        {"deadline": 30, "impact": 30, "mission_type": 20, "dependency": 10, "recurrence": 10},
        "Maximum de points par critère A-E (somme ≤ 100)."),
    "df.coefficient_by_position": (
        {"1": 10, "2": 8, "3": 5, "4": 4},
        "Coefficient du domaine selon sa position dans imperium_user_priorities (×10/8/5/4, doc 52)."),
    "df.priority_buckets": (
        {"thresholds": [[700, 10], [600, 9], [500, 8], [400, 7], [300, 6], [200, 5], [100, 4], [50, 3], [20, 2]],
         "floor": 1},
        "Bucket de priorité 1-10 selon le score pondéré : [seuil, bucket], sinon `floor`."),
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, (value, rationale) in PARAMETERS.items():
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, 'df', %s::jsonb, 'points', %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, json.dumps(value), rationale + " Semé depuis les constantes du code (spec Daily §4)."),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", (list(PARAMETERS),))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
