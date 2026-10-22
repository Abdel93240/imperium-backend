"""pulse: recettes par Nexus et Nourrir l'IA, estimation des repas « Autre » (bloc 1, 2026-10-22)

- Chatbot : action `add_recipe` (carte validée par l'utilisateur) ; ajoutée à l'agent Général s'il existe.
- Nourrir l'IA : destination `recipe` (recette lue sur le document, corrigée puis rangée dans le catalogue Pulse).
- Slots locaux semés éteints : `pulse.meal_estimate` (apports estimés depuis la description d'un repas hors stock,
  toujours marqués « estimation ») et `pulse.recipe_extract` (recette structurée depuis un texte déposé).

Revision ID: 20261022_0135
Revises: 20261022_0134
Create Date: 2026-10-22
"""

import json
import uuid
from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0135"
down_revision: str | None = "20261022_0134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIONS_BEFORE = "('create_project', 'add_project_mission', 'create_mission', 'create_routine', 'add_event', 'switch_agent')"
ACTIONS_AFTER = ("('create_project', 'add_project_mission', 'create_mission', 'create_routine', 'add_event', "
                 "'add_recipe', 'switch_agent')")
DESTINATIONS_BEFORE = "('memory', 'project', 'lab_results')"
DESTINATIONS_AFTER = "('memory', 'project', 'lab_results', 'recipe')"
RATIONALE = "Agent Général : peut proposer d'ajouter une recette au catalogue Pulse (add_recipe), migration 0135."
SLOTS = [
    ("pulse.meal_estimate", "Apports estimés (kcal, protéines, glucides, lipides) d'un repas décrit hors stock, "
                            "toujours marqués estimation et corrigeables."),
    ("pulse.recipe_extract", "Recette structurée (portions, ingrédients, étapes, conditionnement) lue dans un texte "
                             "déposé dans Nourrir l'IA, à corriger avant validation."),
]


def upgrade() -> None:
    op.drop_constraint("source_check", "pulse_recipes", type_="check")
    op.create_check_constraint("source_check", "pulse_recipes", "source IN ('planner', 'chatbot', 'manual', 'inbox')")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {ACTIONS_AFTER}")
    op.drop_constraint("destination_check", "knowledge_inbox_items", type_="check")
    op.create_check_constraint("destination_check", "knowledge_inbox_items",
                               f"destination IS NULL OR destination IN {DESTINATIONS_AFTER}")
    conn = op.get_bind()
    for slot, notes in SLOTS:
        conn.exec_driver_sql(
            "INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr) "
            "VALUES (gen_random_uuid(), %s, 'pulse', 'local_default', 100, 92, %s) "
            "ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING", (slot, notes))
    row = conn.exec_driver_sql(
        "SELECT id, domain, value, unit, version FROM parameters WHERE code = 'chat.agents' AND superseded_by IS NULL "
        "ORDER BY version DESC LIMIT 1").first()
    if row is None:
        return
    value = row.value if isinstance(row.value, dict) else json.loads(row.value)
    actions = (value.get("general") or {}).get("actions")
    if not isinstance(actions, list) or "add_recipe" in actions:
        return
    value["general"]["actions"] = [*actions, "add_recipe"]
    new_id = uuid.uuid4()
    conn.exec_driver_sql(
        "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
        "VALUES (%s, 'chat.agents', %s, %s::jsonb, %s, %s, 'seed', %s)",
        (new_id, row.domain, json.dumps(value), row.unit, RATIONALE, row.version + 1))
    conn.exec_driver_sql("UPDATE parameters SET superseded_by = %s WHERE id = %s", (new_id, row.id))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        found = conn.exec_driver_sql("SELECT id FROM parameters WHERE code = 'chat.agents' AND rationale_fr = %s",
                                     (RATIONALE,)).first()
        if found is not None:
            conn.exec_driver_sql("UPDATE parameters SET superseded_by = NULL WHERE superseded_by = %s", (found.id,))
            conn.exec_driver_sql("DELETE FROM parameters WHERE id = %s", (found.id,))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", ([s[0] for s in SLOTS],))
    op.execute("DELETE FROM chat_proposals WHERE action = 'add_recipe'")
    op.execute("UPDATE knowledge_inbox_items SET destination = NULL WHERE destination = 'recipe'")
    op.drop_constraint("destination_check", "knowledge_inbox_items", type_="check")
    op.create_check_constraint("destination_check", "knowledge_inbox_items",
                               f"destination IS NULL OR destination IN {DESTINATIONS_BEFORE}")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {ACTIONS_BEFORE}")
    op.execute("UPDATE pulse_recipes SET source = 'manual' WHERE source = 'inbox'")
    op.drop_constraint("source_check", "pulse_recipes", type_="check")
    op.create_check_constraint("source_check", "pulse_recipes", "source IN ('planner', 'chatbot', 'manual')")
