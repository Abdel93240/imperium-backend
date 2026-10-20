"""chatbot: switching agent mid-conversation is a proposal the user validates (doc 72 §2, §4)

Quand la discussion porte sur un sujet qu'un autre agent gère, le modèle peut proposer de changer d'agent ; c'est
une proposition comme une autre (`switch_agent`), affichée en carte, que l'utilisateur valide ou refuse. La
validation change l'agent et le contexte de la session ; la proposition reste comme trace du changement.

Revision ID: 20261020_0118
Revises: 20261020_0117
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261020_0118"
down_revision: str | None = "20261020_0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('create_project', 'add_project_mission', 'create_routine')"
AFTER = "('create_project', 'add_project_mission', 'create_routine', 'switch_agent')"


def upgrade() -> None:
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {AFTER}")


def downgrade() -> None:
    op.execute("DELETE FROM chat_proposals WHERE action = 'switch_agent'")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {BEFORE}")
