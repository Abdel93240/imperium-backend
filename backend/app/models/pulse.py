"""Règles rouges, signalements subjectifs et sentinelle Pulse (spec Pulse §3.2, §3.5, §5, §11, §14 ;
CHECK constraints live in migrations 0106, 0108, 0109, 0111, 0112 ; métriques 0110)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class PulseRedFlagRule(UUIDPrimaryKeyMixin, Base):
    """Règle globale semée ; `active` ne bascule que par SQL (jamais par une route ni par un modèle)."""

    __tablename__ = "pulse_red_flag_rules"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    message_fr: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PulseRedFlagEvent(UUIDPrimaryKeyMixin, Base):
    """Levée d'une règle : preuve sans texte libre, ouverte tant que l'utilisateur ne l'a pas résolue."""

    __tablename__ = "pulse_red_flag_events"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_red_flag_rules.id"), nullable=False)
    subject_ref: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    acknowledged_by_user_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PulseSubjectiveReport(UUIDPrimaryKeyMixin, Base):
    """Signalement fatigue | mood | stress, niveau 1 (bien) → 5 (mal) ; suppression réelle à la demande."""

    __tablename__ = "pulse_subjective_reports"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PulseSentinelRule(UUIDPrimaryKeyMixin, Base):
    """Règle S1-S7 globale semée inactive ; `active` ne bascule que par SQL."""

    __tablename__ = "pulse_sentinel_rules"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cooldown_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_dispatch_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PulseBoardSnapshot(UUIDPrimaryKeyMixin, Base):
    """Copie figée du board au réveil (reproductibilité), prise avant l'interprète."""

    __tablename__ = "pulse_board_snapshots"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    board: Mapped[dict] = mapped_column(JSONB, nullable=False)
    flags_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_severity: Mapped[str] = mapped_column(Text, nullable=False)


class PulseDispatchLog(UUIDPrimaryKeyMixin, Base):
    """Un réveil de la sentinelle : `queued` puis `done` par le runner (essai à blanc tant que l'IA est coupée)."""

    __tablename__ = "pulse_dispatch_log"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    board_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_board_snapshots.id", ondelete="CASCADE"), nullable=False)
    flag_set: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trigger_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    procedures_named: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    reacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PulseMetricsDaily(UUIDPrimaryKeyMixin, Base):
    """Compteurs d'un jour de Paris (spec Pulse §3.9 + user_id) ; NULL = pas encore mesurable."""

    __tablename__ = "pulse_metrics_daily"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    dispatches: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_passes: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatches_useful: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatches_useless: Mapped[int] = mapped_column(Integer, nullable=False)
    missed_reports: Mapped[int] = mapped_column(Integer, nullable=False)
    escalations: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_fallbacks: Mapped[int] = mapped_column(Integer, nullable=False)
    red_flags: Mapped[int] = mapped_column(Integer, nullable=False)
    proposals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refused: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solver_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solver_infeasible: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agreement_by_slot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PulseProcedure(UUIDPrimaryKeyMixin, Base):
    """Carte P1-P10 globale semée inactive (spec Pulse §7) ; `active` ne bascule que par SQL."""

    __tablename__ = "pulse_procedures"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_fr: Mapped[str] = mapped_column(Text, nullable=False)
    purpose_fr: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    llm_slots: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PulseProcedureRun(UUIDPrimaryKeyMixin, Base):
    """Exécution d'une procédure nommée : `queued` puis le runner, une entrée de journal par étape."""

    __tablename__ = "pulse_procedure_runs"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    procedure_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_procedures.id"), nullable=False)
    procedure_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatch_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_dispatch_log.id", ondelete="SET NULL"), nullable=True)
    trigger_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    steps_log: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PulseProposal(UUIDPrimaryKeyMixin, Base):
    """Proposition refusable ; en essai à blanc elle n'est jamais présentée, rien ne s'applique sans décision."""

    __tablename__ = "pulse_proposals"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    procedure_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_procedure_runs.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_fr: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PulseProgram(UUIDPrimaryKeyMixin, Base):
    """Programme d'entraînement (spec Pulse §3.6 + user_id) ; un seul `active` par utilisateur."""

    __tablename__ = "pulse_programs"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    objective_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mesocycle: Mapped[dict] = mapped_column(JSONB, nullable=False)
    doctrine_sheet_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_run: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_procedure_runs.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PulseProgramTarget(UUIDPrimaryKeyMixin, Base):
    """Séries cibles d'un groupe musculaire pour une semaine (lundi de Paris)."""

    __tablename__ = "pulse_program_targets"

    program_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_programs.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    muscle_group: Mapped[str] = mapped_column(Text, nullable=False)
    target_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    tolerance_sets: Mapped[int] = mapped_column(Integer, nullable=False, default=2)


class PulseVolumeDebt(UUIDPrimaryKeyMixin, Base):
    """Séries dues par groupe : open → scheduled (séance de remboursement) → repaid ; perte = décision WR."""

    __tablename__ = "pulse_volume_debt"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    program_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_programs.id", ondelete="CASCADE"), nullable=False)
    muscle_group: Mapped[str] = mapped_column(Text, nullable=False)
    debt_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_workout_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_workouts.id", ondelete="CASCADE"), nullable=False)
    repayment_workout_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_workouts.id", ondelete="SET NULL"), nullable=True)
    created_by_proposal: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_proposals.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PulseLegalMove(UUIDPrimaryKeyMixin, Base):
    """Coup du §8 : préconditions, paramètres et effets documentés ; évalués en code, `active` par SQL."""

    __tablename__ = "pulse_legal_moves"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_fr: Mapped[str] = mapped_column(Text, nullable=False)
    preconditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parameters_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    effects: Mapped[dict] = mapped_column(JSONB, nullable=False)
    doctrine_refs: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# --- Diète (doc 40 §10.4–§10.9, migration 0131) -----------------------------------------------------------------

class PulseDietPlan(UUIDPrimaryKeyMixin, Base):
    """Plan d'une semaine (lundi) : demandé → proposé par le cerveau → validé (un seul `active` par semaine)."""

    __tablename__ = "pulse_diet_plans"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())


class PulseRecipe(UUIDPrimaryKeyMixin, Base):
    """Recette du catalogue : ingrédients [{name, quantity, unit}] pour `servings` portions, étapes, conditionnement
    et conservation, apports PAR PORTION (facultatifs)."""

    __tablename__ = "pulse_recipes"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    servings: Mapped[int] = mapped_column(Integer, nullable=False)
    portion_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    ingredients: Mapped[list] = mapped_column(JSONB, nullable=False)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    packaging: Mapped[list] = mapped_column(JSONB, nullable=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_diet_plans.id", ondelete="SET NULL"),
                                                 nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())


class PulsePreparation(UUIDPrimaryKeyMixin, Base):
    """Préparation (batch cooking) d'une recette : consomme les ingrédients, crée une ligne de portions."""

    __tablename__ = "pulse_preparations"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"),
                                          nullable=False)
    recipe_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_recipes.id"), nullable=False)
    planned_day: Mapped[date] = mapped_column(Date(), nullable=False)
    portions_planned: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned")
    missing: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    portions_made: Mapped[int | None] = mapped_column(Integer, nullable=True)
    portion_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    stock_item_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("food_stock_items.id"), nullable=True)
    consumed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    complete_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    complete_request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())


class PulseDietPlanMeal(UUIDPrimaryKeyMixin, Base):
    """Repas prévu : un créneau d'un jour, une recette, des portions ; `eaten` quand un repas validé le désigne."""

    __tablename__ = "pulse_diet_plan_meals"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"),
                                          nullable=False)
    day: Mapped[date] = mapped_column(Date(), nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    recipe_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_recipes.id"), nullable=False)
    portions: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned")
    meal_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_meals.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())


class PulseShoppingItem(UUIDPrimaryKeyMixin, Base):
    """Ligne de courses née d'un plan validé ; `bought` quand le stock la couvre, `removed` à la demande."""

    __tablename__ = "pulse_shopping_items"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_diet_plans.id", ondelete="CASCADE"),
                                          nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                 onupdate=func.now())


class PulseLabResult(UUIDPrimaryKeyMixin, Base):
    """Valeur d'analyse VALIDÉE par l'utilisateur (prise de sang via Nourrir l'IA, ou saisie) ; migration 0132."""

    __tablename__ = "pulse_lab_results"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    inbox_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_inbox_items.id", ondelete="SET NULL"), nullable=True)
    analyte: Mapped[str] = mapped_column(Text, nullable=False)
    analyte_key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    ref_high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    ref_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_on: Mapped[date] = mapped_column(Date(), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
