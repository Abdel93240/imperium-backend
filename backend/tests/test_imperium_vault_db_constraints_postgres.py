"""PostgreSQL checks for Patch 9J Vault ledger invariants.

These tests require a migrated PostgreSQL database. They skip locally when
IMPERIUM_TEST_DATABASE_URL is not set and fail in CI if the variable is missing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("Vault ledger DB constraint tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


def _make_user(conn) -> str:
    user_id = str(uuid4())
    conn.execute(
        text(
            "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
            "VALUES (:id, :email, FALSE, now(), now())"
        ),
        {"id": user_id, "email": f"vault-db-{user_id}@example.test"},
    )
    return user_id


def _insert_vault_transaction(
    conn,
    *,
    user_id: str,
    amount_cents: int = 1000,
    is_reversal: bool = False,
    reversal_of_transaction_id: str | None = None,
) -> str:
    transaction_id = str(uuid4())
    occurred_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    conn.execute(
        text(
            "INSERT INTO imperium_vault_transactions "
            "(id, user_id, transaction_type, amount_cents, currency, occurred_at, local_date, timezone, "
            "category, source, is_reversal, reversal_of_transaction_id, created_at, updated_at) "
            "VALUES (:id, :user_id, 'income', :amount_cents, 'EUR', :occurred_at, "
            ":local_date, 'UTC', 'vtc', 'manual', :is_reversal, :reversal_of_transaction_id, now(), now())"
        ),
        {
            "id": transaction_id,
            "user_id": user_id,
            "amount_cents": amount_cents,
            "occurred_at": occurred_at,
            "local_date": occurred_at.date(),
            "is_reversal": is_reversal,
            "reversal_of_transaction_id": reversal_of_transaction_id,
        },
    )
    return transaction_id


def _expect_constraint_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "check" in msg or "unique" in msg or "violates" in msg or "constraint" in msg, (
        f"Expected database constraint error, got: {exc!r}"
    )


def _expect_append_only_failure(exc: Exception) -> None:
    msg = str(exc).lower()
    assert "append-only" in msg or "trigger" in msg or "forbidden" in msg, (
        f"Expected append-only trigger error, got: {exc!r}"
    )


def test_imperium_vault_transactions_reject_non_positive_amount_cents(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_vault_transaction(conn, user_id=user_id, amount_cents=0)

    _expect_constraint_failure(excinfo.value)


def test_imperium_vault_transactions_insert_is_allowed(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        transaction_id = _insert_vault_transaction(conn, user_id=user_id)
        stored_id = conn.execute(
            text("SELECT id FROM imperium_vault_transactions WHERE id = :id"),
            {"id": transaction_id},
        ).scalar_one()

    assert str(stored_id) == transaction_id


def test_imperium_vault_transactions_update_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        transaction_id = _insert_vault_transaction(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE imperium_vault_transactions SET amount_cents = 2000 WHERE id = :id"),
                {"id": transaction_id},
            )

    _expect_append_only_failure(excinfo.value)


def test_imperium_vault_transactions_delete_is_rejected_by_trigger(engine) -> None:
    with engine.begin() as conn:
        user_id = _make_user(conn)
        transaction_id = _insert_vault_transaction(conn, user_id=user_id)

    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM imperium_vault_transactions WHERE id = :id"),
                {"id": transaction_id},
            )

    _expect_append_only_failure(excinfo.value)


def test_imperium_vault_transactions_truncate_is_rejected_by_trigger(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE imperium_vault_transactions"))

    _expect_append_only_failure(excinfo.value)


def test_imperium_vault_transactions_reject_incoherent_reversal_link(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            _insert_vault_transaction(conn, user_id=user_id, is_reversal=True)

    _expect_constraint_failure(excinfo.value)


def test_imperium_vault_transactions_allow_only_one_reversal_per_original(engine) -> None:
    with pytest.raises(Exception) as excinfo:
        with engine.begin() as conn:
            user_id = _make_user(conn)
            original_id = _insert_vault_transaction(conn, user_id=user_id)
            _insert_vault_transaction(
                conn,
                user_id=user_id,
                is_reversal=True,
                reversal_of_transaction_id=original_id,
            )
            _insert_vault_transaction(
                conn,
                user_id=user_id,
                is_reversal=True,
                reversal_of_transaction_id=original_id,
            )

    _expect_constraint_failure(excinfo.value)
