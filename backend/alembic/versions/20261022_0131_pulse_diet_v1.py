"""pulse: diet V1 (lot B du kit, 2026-10-22) — recettes, plan de la semaine, préparation en portions, courses

Doc 40 §10.4–§10.9 : le cerveau propose la semaine (recettes, préparations, repas), l'utilisateur la valide ;
cuisiner consomme les ingrédients du stock et crée les portions (même poids pour toutes), manger consomme ces
portions ; la liste de courses = besoins des préparations moins le stock, elle se vide quand le stock arrive.

Tout est semé éteint : `pulse.diet_enabled` (routes), `pulse.diet_missions_enabled` (missions Imperium « faire
les courses » / « cuisiner »), le job `pulse.diet_planner` et les deux slots du planificateur.

Revision ID: 20261022_0131
Revises: 20261022_0130
Create Date: 2026-10-22
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0131"
down_revision: str | None = "20261022_0130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
SOURCES_BEFORE = "('manual', 'vault_receipt', 'pantry_scan', 'chatbot')"
SOURCES_AFTER = "('manual', 'vault_receipt', 'pantry_scan', 'chatbot', 'preparation')"
MACROS = ("calories", "protein_g", "carbs_g", "fat_g")
PARAMETERS = [
    ("pulse.diet_enabled", "pulse", False, None,
     "Diète Pulse (recettes, plan de la semaine, préparations, courses) : routes ouvertes."),
    ("pulse.diet_missions_enabled", "pulse", False, None,
     "Un plan validé crée les missions Imperium « Faire les courses » et « Cuisiner »."),
]
SLOTS = [
    ("pulse.diet_weekly_program", "cloud_forced",
     "Plan de la semaine : recettes, préparations et repas (rôle santé), proposé puis validé par l'utilisateur."),
    ("pulse.diet_weekly_program_local", "local_default",
     "Plan de la semaine par le modèle local, quand le rôle santé n'est pas disponible."),
]


def _macros() -> list[sa.Column]:
    return [sa.Column(name, sa.Numeric(7 if name == "calories" else 6, 1), nullable=True) for name in MACROS]


def _stamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def _user() -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "pulse_diet_plans",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("rationale_fr", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trace", JSONB, nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("status IN ('generating', 'proposed', 'active', 'superseded', 'rejected', 'failed')",
                           name="status_check"),
        sa.CheckConstraint("source IS NULL OR source IN ('cloud', 'local')", name="source_check"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_pulse_diet_plans_user_key"),
    )
    op.create_index("pulse_diet_plans_one_active", "pulse_diet_plans", ["user_id", "week_start"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "pulse_recipes",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("portion_weight_g", sa.Numeric(7, 1), nullable=True),
        sa.Column("ingredients", JSONB, nullable=False),
        sa.Column("steps", JSONB, nullable=False),
        sa.Column("packaging", JSONB, nullable=False),
        sa.Column("shelf_life_days", sa.Integer(), nullable=True),
        *_macros(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("plan_id", UUID, sa.ForeignKey("pulse_diet_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("request_hash", sa.Text(), nullable=True),
        *_stamps(),
        sa.CheckConstraint("servings > 0", name="servings_positive"),
        sa.CheckConstraint("shelf_life_days IS NULL OR shelf_life_days >= 0", name="shelf_life"),
        sa.CheckConstraint("source IN ('planner', 'chatbot', 'manual')", name="source_check"),
        sa.CheckConstraint("status IN ('proposed', 'active', 'archived')", name="status_check"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_pulse_recipes_user_key"),
    )

    op.create_table(
        "pulse_preparations",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("plan_id", UUID, sa.ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipe_id", UUID, sa.ForeignKey("pulse_recipes.id"), nullable=False),
        sa.Column("planned_day", sa.Date(), nullable=False),
        sa.Column("portions_planned", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("missing", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("portions_made", sa.Integer(), nullable=True),
        sa.Column("portion_weight_g", sa.Numeric(7, 1), nullable=True),
        sa.Column("stock_item_id", UUID, sa.ForeignKey("food_stock_items.id"), nullable=True),
        sa.Column("consumed", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("complete_idempotency_key", sa.Text(), nullable=True),
        sa.Column("complete_request_hash", sa.Text(), nullable=True),
        *_stamps(),
        sa.CheckConstraint("portions_planned > 0", name="portions_planned"),
        sa.CheckConstraint("portions_made IS NULL OR portions_made > 0", name="portions_made"),
        sa.CheckConstraint("status IN ('planned', 'started', 'done', 'cancelled')",
                           name="status_check"),
    )
    op.create_index("pulse_preparations_plan_idx", "pulse_preparations", ["plan_id"])

    op.create_table(
        "pulse_diet_plan_meals",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("plan_id", UUID, sa.ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("recipe_id", UUID, sa.ForeignKey("pulse_recipes.id"), nullable=False),
        sa.Column("portions", sa.Numeric(4, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("meal_id", UUID, sa.ForeignKey("pulse_meals.id"), nullable=True),
        *_stamps(),
        sa.CheckConstraint("portions > 0", name="portions_positive"),
        sa.CheckConstraint("slot IN ('breakfast', 'lunch', 'dinner', 'snack')", name="slot_check"),
        sa.CheckConstraint("status IN ('planned', 'eaten', 'skipped')", name="status_check"),
    )
    op.create_index("pulse_diet_plan_meals_plan_idx", "pulse_diet_plan_meals", ["plan_id", "day"])

    op.create_table(
        "pulse_shopping_items",
        sa.Column("id", UUID, primary_key=True),
        _user(),
        sa.Column("plan_id", UUID, sa.ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("unit IN ('piece', 'kg', 'g', 'l', 'cl', 'ml')", name="unit_check"),
        sa.CheckConstraint("status IN ('open', 'bought', 'removed', 'superseded')",
                           name="status_check"),
    )
    op.create_index("pulse_shopping_items_user_status_idx", "pulse_shopping_items", ["user_id", "status"])

    op.add_column("food_stock_items", sa.Column("kind", sa.Text(), nullable=False, server_default="raw"))
    op.add_column("food_stock_items", sa.Column("recipe_id", UUID, sa.ForeignKey("pulse_recipes.id"), nullable=True))
    op.add_column("food_stock_items", sa.Column("portion_weight_g", sa.Numeric(7, 1), nullable=True))
    for column in _macros():
        op.add_column("food_stock_items", column)
    op.create_check_constraint("kind_check", "food_stock_items", "kind IN ('raw', 'prepared')")
    op.drop_constraint("source_check", "food_stock_items", type_="check")
    op.create_check_constraint("source_check", "food_stock_items", f"source IN {SOURCES_AFTER}")
    op.add_column("pulse_meals", sa.Column("plan_meal_id", UUID, sa.ForeignKey("pulse_diet_plan_meals.id"),
                                           nullable=True))

    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
            "VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1) "
            "ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING",
            (code, domain, json.dumps(value), unit, rationale))
    for slot, tier, notes in SLOTS:
        conn.exec_driver_sql(
            "INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr) "
            "VALUES (gen_random_uuid(), %s, 'pulse', %s, 100, 92, %s) "
            "ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING", (slot, tier, notes))
    conn.exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'pulse.diet_planner', 'event_subscription', NULL, %s, "
        "'app.services.pulse.diet_planner:diet_planner_job', false, true, 900) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING", (["pulse.diet.plan_requested"],))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = 'pulse.diet_planner'")
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", ([s[0] for s in SLOTS],))
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_column("pulse_meals", "plan_meal_id")
    op.execute("DELETE FROM food_stock_items WHERE source = 'preparation'")
    op.drop_constraint("source_check", "food_stock_items", type_="check")
    op.create_check_constraint("source_check", "food_stock_items", f"source IN {SOURCES_BEFORE}")
    op.drop_constraint("kind_check", "food_stock_items", type_="check")
    for name in (*MACROS, "portion_weight_g", "recipe_id", "kind"):
        op.drop_column("food_stock_items", name)
    op.drop_table("pulse_shopping_items")
    op.drop_table("pulse_diet_plan_meals")
    op.drop_table("pulse_preparations")
    op.drop_table("pulse_recipes")
    op.drop_table("pulse_diet_plans")
