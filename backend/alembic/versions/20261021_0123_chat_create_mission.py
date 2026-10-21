"""chat: the General agent may propose a project-less mission (create_mission)

Missions hors projet (paperasse, démarches… ; décision utilisateur 2026-10-21) : l'action `create_mission` du
chatbot est ajoutée à la liste des actions de l'agent Général dans `chat.agents` (nouvelle version du
paramètre, le reste de la fiche inchangé ; rien si l'agent n'a pas de liste ou l'a déjà) et à la contrainte des
propositions.

Revision ID: 20261021_0123
Revises: 20261021_0122
Create Date: 2026-10-21
"""

import json
import uuid
from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0123"
down_revision: str | None = "20261021_0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('create_project', 'add_project_mission', 'create_routine', 'switch_agent')"
AFTER = "('create_project', 'add_project_mission', 'create_mission', 'create_routine', 'switch_agent')"
RATIONALE = "Agent Général : peut proposer une mission hors projet (create_mission), migration 0123."


def upgrade() -> None:
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {AFTER}")
    conn = op.get_bind()
    row = conn.exec_driver_sql(
        "SELECT id, domain, value, unit, version FROM parameters WHERE code = 'chat.agents' AND superseded_by IS NULL "
        "ORDER BY version DESC LIMIT 1").first()
    if row is None:
        return
    value = row.value if isinstance(row.value, dict) else json.loads(row.value)
    actions = (value.get("general") or {}).get("actions")
    if not isinstance(actions, list) or "create_mission" in actions:
        return
    position = actions.index("add_project_mission") + 1 if "add_project_mission" in actions else len(actions)
    value["general"]["actions"] = [*actions[:position], "create_mission", *actions[position:]]
    new_id = uuid.uuid4()
    conn.exec_driver_sql(
        "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
        "VALUES (%s, 'chat.agents', %s, %s::jsonb, %s, %s, 'seed', %s)",
        (new_id, row.domain, json.dumps(value), row.unit, RATIONALE, row.version + 1))
    conn.exec_driver_sql("UPDATE parameters SET superseded_by = %s WHERE id = %s", (new_id, row.id))


def downgrade() -> None:
    op.execute("DELETE FROM chat_proposals WHERE action = 'create_mission'")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {BEFORE}")
    conn = op.get_bind()
    row = conn.exec_driver_sql(
        "SELECT id, version FROM parameters WHERE code = 'chat.agents' AND rationale_fr = %s", (RATIONALE,)).first()
    if row is None:
        return
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("UPDATE parameters SET superseded_by = NULL WHERE superseded_by = %s", (row.id,))
        conn.exec_driver_sql("DELETE FROM parameters WHERE id = %s", (row.id,))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
