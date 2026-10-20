"""chatbot: per-action requirement sheets (editable data), project proposals carry their first missions (doc 72 §5, §6.2 ; doc 71 §5, §7)

`chat.action_requirements` (jsonb) : pour chaque action, les informations à réunir AVANT de proposer et la
question à poser quand elles manquent. Le code refuse une proposition incomplète (le modèle doit demander) ;
modifier la fiche change le comportement sans toucher au code, comme la grille de détection du doc 72 §6.2.
Un projet doit naître complet (doc 71 §7 : un projet incomplet est inerte) : objectif et premières missions,
validés en une seule fois (doc 72 §5).

Revision ID: 20261020_0116
Revises: 20261020_0115
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261020_0116"
down_revision: str | None = "20261020_0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIREMENTS = {
    "create_project": {
        "required": [["title", "le nom du projet"], ["description", "le résultat que tu vises avec ce projet"], ["missions", "ses premières étapes (au moins une mission)"]],
        "min_description_chars": 15, "min_missions": 1, "max_missions": 10,
    },
    "add_project_mission": {"required": [["project_id", "le projet concerné"], ["title", "ce que la mission consiste à faire"]]},
    "create_routine": {"required": [["name", "le nom de la routine"], ["frequency", "sa fréquence (chaque jour, semaine, 2 semaines ou mois)"]]},
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'chat.action_requirements', 'imperium', %s::jsonb, 'json',
                'Informations à réunir avant de proposer chaque action du chatbot (doc 72 §6.2 : donnée éditable).',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """,
        (json.dumps(REQUIREMENTS, ensure_ascii=False),),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM parameters WHERE code = 'chat.action_requirements'")
    op.execute("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
