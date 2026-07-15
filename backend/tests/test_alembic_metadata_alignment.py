from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql.base import PGDialect

from app.db.base import Base
from app.db.postgres_types import Vector1024, register_postgresql_vector_type
from app.models.ai import AIMemory
from app.models.auth import Device, RefreshToken, User
from app.models.imperium import ImperiumMemoryCandidateDecision
from app.models.vault import LegacyVaultTransaction


def _index_expressions(model, index_name: str) -> list[str]:
    index = next(index for index in model.__table__.indexes if index.name == index_name)
    return [str(expression) for expression in index.expressions]


def test_legacy_vault_transactions_stays_declared_for_alembic_metadata() -> None:
    assert LegacyVaultTransaction.__tablename__ == "vault_transactions"
    assert Base.metadata.tables["vault_transactions"] is LegacyVaultTransaction.__table__

    columns = set(LegacyVaultTransaction.__table__.columns.keys())
    assert {
        "id",
        "user_id",
        "event_id",
        "occurred_at",
        "local_date",
        "timezone",
        "transaction_type",
        "wallet",
        "category",
        "label",
        "amount",
        "currency",
        "notes",
        "source_app",
        "created_at",
        "updated_at",
    } <= columns

    constraint_names = {
        constraint.name
        for constraint in LegacyVaultTransaction.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    for expected_name in {
        "vault_transactions_transaction_type_check",
        "vault_transactions_wallet_check",
        "vault_transactions_amount_positive",
    }:
        assert any(name.endswith(expected_name) for name in constraint_names)

    index_names = {index.name for index in LegacyVaultTransaction.__table__.indexes}
    assert {
        "vault_transactions_user_local_date_idx",
        "vault_transactions_user_occurred_at_idx",
        "vault_transactions_user_transaction_type_idx",
    } <= index_names


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
    legacy_vault_expressions = _index_expressions(
        LegacyVaultTransaction,
        "vault_transactions_user_occurred_at_idx",
    )

    assert memory_candidate_expressions[0].endswith("user_id")
    assert memory_candidate_expressions[1] == "created_at DESC"
    assert legacy_vault_expressions[0].endswith("user_id")
    assert legacy_vault_expressions[1] == "occurred_at DESC"


def test_pgvector_type_is_registered_for_alembic_reflection() -> None:
    register_postgresql_vector_type()

    assert PGDialect.ischema_names["vector"] is Vector1024
    assert AIMemory.__table__.columns["embedding"].type.get_col_spec() == "vector(1024)"
    assert Vector1024("1024").get_col_spec() == "vector(1024)"
