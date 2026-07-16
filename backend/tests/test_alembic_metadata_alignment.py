from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql.base import PGDialect

from app.db.base import Base
from app.db.postgres_types import Vector1024, register_postgresql_vector_type
from app.models.ai import AIMemory
from app.models.auth import Device, RefreshToken, User
from app.models.imperium import ImperiumMemoryCandidateDecision
from app.models.vault import PressureSnapshot, UpcomingExpense, WeeklyFinanceSummary


def _index_expressions(model, index_name: str) -> list[str]:
    index = next(index for index in model.__table__.indexes if index.name == index_name)
    return [str(expression) for expression in index.expressions]


def test_vault_phase_e_tables_are_declared_for_alembic_metadata() -> None:
    assert "vault_transactions" not in Base.metadata.tables
    assert Base.metadata.tables["upcoming_expenses"] is UpcomingExpense.__table__
    assert Base.metadata.tables["weekly_finance_summaries"] is WeeklyFinanceSummary.__table__
    assert Base.metadata.tables["pressure_snapshots"] is PressureSnapshot.__table__

    upcoming_columns = set(UpcomingExpense.__table__.columns.keys())
    assert {
        "id",
        "user_id",
        "label_fr",
        "amount",
        "due_date",
        "recurrence",
        "category",
        "wallet",
        "mandatory",
        "active",
        "created_at",
        "updated_at",
    } <= upcoming_columns

    weekly_columns = set(WeeklyFinanceSummary.__table__.columns.keys())
    assert {
        "user_id",
        "week_start",
        "business_revenue",
        "business_expenses",
        "weekly_business_profit",
        "personal_expenses",
        "computed_at",
        "detail",
    } <= weekly_columns
    assert [column.name for column in WeeklyFinanceSummary.__table__.primary_key.columns] == ["user_id", "week_start"]

    pressure_columns = set(PressureSnapshot.__table__.columns.keys())
    assert "user_id" in pressure_columns

    constraint_names = {
        constraint.name
        for constraint in PressureSnapshot.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert any(name.endswith("pressure_snapshots_score_range") for name in constraint_names)
    assert any(name.endswith("pressure_snapshots_label_check") for name in constraint_names)


def test_auth_metadata_uses_existing_constraint_and_index_names() -> None:
    users_unique_names = {
        constraint.name
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    token_unique_names = {
        constraint.name
        for constraint in RefreshToken.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    device_index_names = {index.name for index in Device.__table__.indexes}

    assert "users_email_unique" in users_unique_names
    assert "refresh_tokens_token_hash_unique" in token_unique_names
    assert "devices_user_status_idx" in device_index_names


def test_desc_indexes_match_existing_migrations() -> None:
    memory_candidate_expressions = _index_expressions(
        ImperiumMemoryCandidateDecision,
        "imperium_memory_candidate_decisions_user_created_idx",
    )
    pressure_expressions = _index_expressions(
        PressureSnapshot,
        "pressure_snapshots_computed_at_idx",
    )
    pressure_user_expressions = _index_expressions(
        PressureSnapshot,
        "pressure_snapshots_user_computed_at_idx",
    )

    assert memory_candidate_expressions[0].endswith("user_id")
    assert memory_candidate_expressions[1] == "created_at DESC"
    assert pressure_expressions[0] == "computed_at DESC"
    assert pressure_user_expressions[0].endswith("user_id")
    assert pressure_user_expressions[1] == "computed_at DESC"


def test_pgvector_type_is_registered_for_alembic_reflection() -> None:
    register_postgresql_vector_type()

    assert PGDialect.ischema_names["vector"] is Vector1024
    assert AIMemory.__table__.columns["embedding"].type.get_col_spec() == "vector(1024)"
    assert Vector1024("1024").get_col_spec() == "vector(1024)"
