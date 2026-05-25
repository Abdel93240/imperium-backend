from pathlib import Path

from sqlalchemy import CheckConstraint

from app.models.imperium import ImperiumMission


def test_imperium_mission_model_enforces_one_active_mission_per_user_contract() -> None:
    index = next(
        idx
        for idx in ImperiumMission.__table__.indexes
        if idx.name == "imperium_missions_one_active_per_user_idx"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["user_id"]
    assert str(index.dialect_options["postgresql"]["where"]) == "status = 'active'"


def test_imperium_mission_status_constraint_accepts_abandoned_status() -> None:
    constraint = next(
        constraint
        for constraint in ImperiumMission.__table__.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name is not None
        and constraint.name.endswith("imperium_missions_status_check")
    )
    constraint_sql = str(constraint.sqltext)

    for status in ("backlog", "active", "completed", "failed", "abandoned", "cancelled"):
        assert f"'{status}'" in constraint_sql


def test_abandoned_status_migration_updates_and_downgrades_check_constraint() -> None:
    migration_text = Path("alembic/versions/20260525_0023_imperium_mission_abandoned_status.py").read_text(
        encoding="utf-8"
    )

    assert 'revision: str = "20260525_0023"' in migration_text
    assert "MISSION_STATUS_CHECK" in migration_text
    assert "LEGACY_MISSION_STATUS_CHECK" in migration_text
    assert "status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled')" in migration_text
    assert "status IN ('backlog', 'active', 'completed', 'failed', 'cancelled')" in migration_text
