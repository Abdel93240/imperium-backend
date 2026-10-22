"""calendar v1 (doc 51, avancé à la demande de l'utilisateur 2026-10-22)

Événements :
- type `blocked_period` (période où des applis sont empêchées : voiture au garage…) ; les événements religieux
  viendront de Path (doc 41) ;
- `all_day`, `urgency` (low | normal | high | critical), `task` (la tâche d'une échéance), `prep_minutes`
  (son temps estimé), `pause_vtc`, `pause_pulse`, `pause_path` (applis impactées, rangées pour leur branchement),
  `status` (active | cancelled | completed | deadline_missed) ;
- récurrence au format RFC 5545 (`recurrence_rrule`, sous-ensemble : FREQ, INTERVAL, BYDAY dont « 3TU »,
  BYMONTHDAY, UNTIL, COUNT) ; occurrences sautées ou déplacées dans `imperium_calendar_overrides` ;
- échéance : `prep_proposal` (créneau de préparation proposé, à valider) et `prep_mission_id` (la mission créée
  à la validation) ; `last_urgent_on` (mission urgente de la veille déjà créée ce jour-là).
Autour :
- journal de sélection : déclencheur `calendar` ; chatbot : action `add_event` (agent Général) ;
- `calendar.event_buffer_minutes` = 15 (marge avant un événement, en attendant les temps de trajet) ;
- slot cloud `calendar.deadline_plan` (premier niveau, semé éteint : sinon proposition par règles) ;
- job `calendar.morning_check` (6 h, semé désactivé) : fenêtre des 7 jours, mission urgente la veille d'une
  échéance, échéance passée sans préparation faite → `deadline_missed`.

Revision ID: 20261022_0129
Revises: 20261022_0128
Create Date: 2026-10-22
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0129"
down_revision: str | None = "20261022_0128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "imperium_calendar_events"
TYPE_CHECK = "ck_imperium_calendar_events_imperium_calendar_events_ev_b570"
TRIGGERS_BEFORE = "('mission_completed', 'day_start', 'disruption_resolved', 'manual', 'replan')"
TRIGGERS_AFTER = "('mission_completed', 'day_start', 'disruption_resolved', 'manual', 'replan', 'calendar')"
ACTIONS_BEFORE = "('create_project', 'add_project_mission', 'create_mission', 'create_routine', 'switch_agent')"
ACTIONS_AFTER = "('create_project', 'add_project_mission', 'create_mission', 'create_routine', 'add_event', 'switch_agent')"
RATIONALE = "Agent Général : peut proposer d'ajouter un événement au calendrier (add_event), migration 0129."
PARAMETERS = [
    ("calendar.event_buffer_minutes", "calendar", 15, "min",
     "Marge laissée avant un événement du calendrier (le trajet n'est pas encore calculé)."),
]


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {TYPE_CHECK}")
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT {TYPE_CHECK} "
               "CHECK (event_type IN ('event', 'deadline', 'vacation', 'blocked_period'))")
    false = sa.text("false")
    for column in (
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=false),
        sa.Column("urgency", sa.Text(), nullable=False, server_default="normal"),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("prep_minutes", sa.Integer(), nullable=True),
        sa.Column("pause_vtc", sa.Boolean(), nullable=False, server_default=false),
        sa.Column("pause_pulse", sa.Boolean(), nullable=False, server_default=false),
        sa.Column("pause_path", sa.Boolean(), nullable=False, server_default=false),
        sa.Column("recurrence_rrule", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("prep_proposal", postgresql.JSONB(), nullable=True),
        sa.Column("prep_mission_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_urgent_on", sa.Date(), nullable=True),
    ):
        op.add_column(TABLE, column)
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT ck_calendar_urgency "
               "CHECK (urgency IN ('low', 'normal', 'high', 'critical'))")
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT ck_calendar_status "
               "CHECK (status IN ('active', 'cancelled', 'completed', 'deadline_missed'))")
    op.create_table(
        "imperium_calendar_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{TABLE}.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("occurrence_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("override_type", sa.Text(), nullable=False),
        sa.Column("new_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("override_type IN ('skip', 'move')", name="calendar_override_type_check"),
        sa.CheckConstraint("override_type = 'skip' OR new_starts_at IS NOT NULL", name="calendar_override_move_check"),
        sa.UniqueConstraint("event_id", "occurrence_at", name="calendar_override_occurrence_unique"),
    )
    op.drop_constraint("daily_selection_log_trigger_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_trigger_check", "daily_selection_log", f"trigger IN {TRIGGERS_AFTER}")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {ACTIONS_AFTER}")
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
            "VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1) "
            "ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING",
            (code, domain, json.dumps(value), unit, rationale))
    op.execute(
        """
        INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'calendar.deadline_plan', 'imperium', 'cloud_forced', 100, 92,
                'Créneau de préparation d''une échéance du calendrier (proposé, à valider).')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'calendar.morning_check', 'cron', '0 4,5 * * *', NULL,
                'app.services.imperium.calendar_threshold:morning_check_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )
    row = conn.exec_driver_sql(
        "SELECT id, domain, value, unit, version FROM parameters WHERE code = 'chat.agents' AND superseded_by IS NULL "
        "ORDER BY version DESC LIMIT 1").first()
    if row is None:
        return
    value = row.value if isinstance(row.value, dict) else json.loads(row.value)
    actions = (value.get("general") or {}).get("actions")
    if not isinstance(actions, list) or "add_event" in actions:
        return
    value["general"]["actions"] = [*actions, "add_event"]
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
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM job_definitions WHERE code = 'calendar.morning_check'")
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'calendar.deadline_plan'")
    op.execute("DELETE FROM chat_proposals WHERE action = 'add_event'")
    op.drop_constraint("chat_proposals_action_check", "chat_proposals", type_="check")
    op.create_check_constraint("chat_proposals_action_check", "chat_proposals", f"action IN {ACTIONS_BEFORE}")
    op.execute("DELETE FROM daily_selection_log WHERE trigger = 'calendar'")
    op.drop_constraint("daily_selection_log_trigger_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_trigger_check", "daily_selection_log", f"trigger IN {TRIGGERS_BEFORE}")
    op.drop_table("imperium_calendar_overrides")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT ck_calendar_status")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT ck_calendar_urgency")
    for name in ("last_urgent_on", "prep_mission_id", "prep_proposal", "status", "recurrence_rrule", "pause_path",
                 "pause_pulse", "pause_vtc", "prep_minutes", "task", "urgency", "all_day"):
        op.drop_column(TABLE, name)
    op.execute(f"UPDATE {TABLE} SET event_type = 'event' WHERE event_type = 'blocked_period'")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {TYPE_CHECK}")
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT {TYPE_CHECK} CHECK (event_type IN ('event', 'deadline', 'vacation'))")
