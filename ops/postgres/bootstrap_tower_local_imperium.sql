\set ON_ERROR_STOP on

\if :{?admin_password}
\else
\echo 'Missing required psql variable: admin_password'
\echo 'Usage: sudo -u postgres psql -d postgres -v admin_password=... -v runtime_password=... -f ops/postgres/bootstrap_tower_local_imperium.sql'
\quit 1
\endif

\if :{?runtime_password}
\else
\echo 'Missing required psql variable: runtime_password'
\echo 'Usage: sudo -u postgres psql -d postgres -v admin_password=... -v runtime_password=... -f ops/postgres/bootstrap_tower_local_imperium.sql'
\quit 1
\endif

SELECT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'imperium_restore_test'
) AS restore_db_exists
\gset

\if :restore_db_exists
\else
\echo 'Missing source database: imperium_restore_test'
\quit 1
\endif

SELECT format('CREATE ROLE imperium_admin LOGIN PASSWORD %L', :'admin_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_admin')
\gexec

SELECT format('CREATE ROLE imperium_user LOGIN PASSWORD %L', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_user')
\gexec

SELECT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'imperium_core'
) AS imperium_core_exists
\gset

\if :imperium_core_exists
\echo 'Database imperium_core already exists; keeping existing database.'
\else
CREATE DATABASE imperium_core OWNER imperium_admin TEMPLATE imperium_restore_test;
\endif

GRANT CONNECT ON DATABASE imperium_core TO imperium_admin;
GRANT CONNECT ON DATABASE imperium_core TO imperium_user;

\connect imperium_core

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

GRANT USAGE ON SCHEMA public TO imperium_admin;
GRANT USAGE ON SCHEMA public TO imperium_user;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO imperium_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO imperium_admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO imperium_admin;

GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO imperium_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO imperium_user;

SELECT format('GRANT UPDATE ON TABLE %I TO imperium_user', table_name)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'devices', 'refresh_tokens', 'idempotency_keys')
\gexec

SELECT format('REVOKE UPDATE, DELETE, TRUNCATE ON TABLE %I FROM imperium_user', table_name)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('events', 'auth_events')
\gexec

SELECT format('GRANT SELECT, INSERT ON TABLE %I TO imperium_user', table_name)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('events', 'auth_events')
\gexec

ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
GRANT SELECT, INSERT ON TABLES TO imperium_user;

ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
GRANT ALL PRIVILEGES ON TABLES TO imperium_admin;

ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO imperium_user;

ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
GRANT ALL PRIVILEGES ON SEQUENCES TO imperium_admin;

SELECT 'current_database=' || current_database();
SELECT 'alembic_version=' || version_num FROM alembic_version;
SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto', 'vector') ORDER BY extname;
