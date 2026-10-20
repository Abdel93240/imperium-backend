"""chatbot: one agent per situation (editable behaviour sheets), session records its agent (doc 72 §2, §3, §6.2)

`chat.agents` (jsonb) : pour chaque agent, son rôle (comment il se comporte), les actions qu'il peut proposer et
s'il est activé. C'est le code qui choisit l'agent selon l'endroit d'où le terminal est ouvert (contexte de la
session), jamais le modèle ; le contexte transmis reste une liste blanche propre à l'agent (code). Les agents
Projet et Mission sont semés désactivés (suggérer, puis l'utilisateur active) : désactivé → agent Général.

Revision ID: 20261020_0117
Revises: 20261020_0116
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0117"
down_revision: str | None = "20261020_0116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENTS = {
    "general": {
        "enabled": True, "label": "Général",
        "role": "Tu es l'assistant général d'Imperium : tu aides l'utilisateur à créer des projets complets, à ajouter "
                "des missions à ses projets et à créer des routines.",
        "actions": ["create_project", "add_project_mission", "create_routine"],
    },
    "project": {
        "enabled": False, "label": "Projet",
        "role": "Tu accompagnes l'utilisateur sur UN seul projet, P1, décrit dans le contexte. Ton rôle : faire avancer "
                "ce projet. Aide-le à clarifier l'objectif et à le découper en missions concrètes et courtes (un verbe "
                "d'action, un résultat vérifiable), dans le bon ordre, avec leur durée. Signale une étape qui semble "
                "manquer pour atteindre l'objectif, mais ne l'ajoute pas sans son accord. Ne parle pas des autres projets.",
        "actions": ["add_project_mission"],
    },
    "mission": {
        "enabled": False, "label": "Mission",
        "role": "Tu accompagnes l'utilisateur pendant UNE mission, décrite dans le contexte. Ton rôle : l'aider à la mener "
                "à bien maintenant. Clarifie la prochaine action concrète, aide-le à se débloquer, et reste très bref pour "
                "ne pas lui faire perdre de temps. Si une suite apparaît, tu peux proposer de l'ajouter comme mission du "
                "même projet (P1).",
        "actions": ["add_project_mission"],
    },
}


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("agent", sa.Text(), nullable=False, server_default="general"))
    op.create_check_constraint("chat_sessions_agent_check", "chat_sessions", "agent IN ('general', 'project', 'mission')")
    conn = op.get_bind()
    conn.exec_driver_sql(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'chat.agents', 'imperium', %s::jsonb, 'json',
                'Agents du chatbot : rôle, actions permises et activation par situation (doc 72 : donnée éditable).',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """,
        (json.dumps(AGENTS, ensure_ascii=False),),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM parameters WHERE code = 'chat.agents'")
    op.execute("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_constraint("chat_sessions_agent_check", "chat_sessions", type_="check")
    op.drop_column("chat_sessions", "agent")
