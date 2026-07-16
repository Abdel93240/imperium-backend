from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from _postgres import require_test_database_url

pytest.importorskip("psycopg")


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("vault phase e constraints"), future=True)
    yield engine
    engine.dispose()


def test_pressure_snapshots_are_append_only(engine) -> None:
    snapshot_id = uuid4()
    with engine.begin() as conn:
        user_id = uuid4()
        conn.execute(
            text(
                "INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                "VALUES (:id, :email, FALSE, now(), now())"
            ),
            {"id": str(user_id), "email": f"vault-phase-e-{user_id}@example.test"},
        )
        conn.execute(
            text(
                "INSERT INTO pressure_snapshots "
                "(id, user_id, computed_at, score, label, factors, daily_targets, inputs_snapshot) "
                "VALUES (:id, :user_id, now(), 30, 'stable', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)"
            ),
            {"id": snapshot_id, "user_id": str(user_id)},
        )

    with engine.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("UPDATE pressure_snapshots SET score = 31 WHERE id = :id"), {"id": snapshot_id})

    with engine.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("DELETE FROM pressure_snapshots WHERE id = :id"), {"id": snapshot_id})

    with engine.begin() as conn, pytest.raises(Exception, match="append-only"):
        conn.execute(text("TRUNCATE TABLE pressure_snapshots"))


def test_phase_e_seeds_exist_and_vault_jobs_are_disabled(engine) -> None:
    with engine.connect() as conn:
        params = {
            row.code
            for row in conn.execute(
                text(
                    "SELECT code FROM parameters WHERE code IN "
                    "('vault.pressure_thresholds', 'vault.category_map', 'vault.horizon_days')"
                )
            )
        }
        assert params == {"vault.pressure_thresholds", "vault.category_map", "vault.horizon_days"}

        signal = conn.execute(
            text("SELECT domain, active FROM signal_definitions WHERE code = 'vault.pressure'")
        ).first()
        assert signal is not None
        assert signal.domain == "vault"
        assert signal.active is True

        jobs = conn.execute(
            text(
                "SELECT code, enabled FROM job_definitions WHERE code IN "
                "('vault.weekly_profit', 'vault.pressure_refresh', 'vault.expenses_horizon')"
            )
        ).all()
        assert {job.code for job in jobs} == {
            "vault.weekly_profit",
            "vault.pressure_refresh",
            "vault.expenses_horizon",
        }
        assert all(job.enabled is False for job in jobs)


def test_legacy_vault_transactions_table_is_dropped_after_dump(engine) -> None:
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'vault_transactions')"
            )
        ).scalar()
        assert exists is False
