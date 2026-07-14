from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SQL = REPO_ROOT / "ops" / "postgres" / "bootstrap_tower_local_imperium.sql"


def test_tower_local_postgres_bootstrap_uses_restore_test_as_safe_source() -> None:
    sql = BOOTSTRAP_SQL.read_text(encoding="utf-8")

    assert "imperium_restore_test" in sql
    assert "CREATE DATABASE imperium_core OWNER imperium_admin TEMPLATE imperium_restore_test" in sql
    assert "DROP DATABASE" not in sql.upper()
    assert "DROPDB" not in sql.upper()
    assert sql.count("imperium_restore_test") == 3


def test_tower_local_postgres_bootstrap_requires_password_variables_without_hardcoded_secrets() -> None:
    sql = BOOTSTRAP_SQL.read_text(encoding="utf-8")

    assert ":{?admin_password}" in sql
    assert ":{?runtime_password}" in sql
    assert "PASSWORD 'REPLACE" not in sql
    assert "PASSWORD '" not in sql
    assert "n8n-postgres" not in sql
    assert "31.97.52.42" not in sql


def test_tower_local_postgres_bootstrap_applies_runtime_role_hardening() -> None:
    sql = BOOTSTRAP_SQL.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO imperium_user" in sql
    assert "REVOKE UPDATE, DELETE, TRUNCATE ON TABLE %I FROM imperium_user" in sql
    assert "AND table_name IN ('events', 'auth_events')" in sql


def test_tower_local_postgres_bootstrap_reassigns_restored_object_ownership_before_grants() -> None:
    sql = BOOTSTRAP_SQL.read_text(encoding="utf-8")

    ownership_index = sql.index("ALTER DATABASE imperium_core OWNER TO imperium_admin;")
    grants_index = sql.index("GRANT USAGE ON SCHEMA public TO imperium_admin;")

    assert ownership_index < grants_index
    assert "ALTER SCHEMA %I OWNER TO imperium_admin" in sql
    assert "ALTER TABLE %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER SEQUENCE %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER VIEW %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER MATERIALIZED VIEW %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER FOREIGN TABLE %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER TYPE %I.%I OWNER TO imperium_admin" in sql
    assert "ALTER FUNCTION %I.%I(%s) OWNER TO imperium_admin" in sql
    assert "ALTER PROCEDURE %I.%I(%s) OWNER TO imperium_admin" in sql
    assert "ALTER AGGREGATE %I.%I(%s) OWNER TO imperium_admin" in sql
    assert "d.classid = 'pg_class'::regclass" in sql
    assert "d.classid = 'pg_type'::regclass" in sql
    assert "d.classid = 'pg_proc'::regclass" in sql
    assert "AND d.deptype = 'e'" in sql
    assert (
        "Restored imperium_core objects must be owned by imperium_admin; found % objects "
        "owned by another role"
    ) in sql
