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

ALTER DATABASE imperium_core OWNER TO imperium_admin;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- CREATE DATABASE ... TEMPLATE copies restored object owners from the source database.
-- Normalize application object ownership before applying runtime grants.
SELECT format('ALTER SCHEMA %I OWNER TO imperium_admin', n.nspname)
FROM pg_namespace n
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND pg_get_userbyid(n.nspowner) <> 'imperium_admin'
\gexec

SELECT format(
    CASE c.relkind
        WHEN 'S' THEN 'ALTER SEQUENCE %I.%I OWNER TO imperium_admin'
        WHEN 'v' THEN 'ALTER VIEW %I.%I OWNER TO imperium_admin'
        WHEN 'm' THEN 'ALTER MATERIALIZED VIEW %I.%I OWNER TO imperium_admin'
        WHEN 'f' THEN 'ALTER FOREIGN TABLE %I.%I OWNER TO imperium_admin'
        ELSE 'ALTER TABLE %I.%I OWNER TO imperium_admin'
    END,
    n.nspname,
    c.relname
)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
  AND pg_get_userbyid(c.relowner) <> 'imperium_admin'
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend d
      WHERE d.classid = 'pg_class'::regclass
        AND d.objid = c.oid
        AND d.deptype = 'e'
  )
ORDER BY n.nspname, c.relname
\gexec

SELECT format('ALTER TYPE %I.%I OWNER TO imperium_admin', n.nspname, t.typname)
FROM pg_type t
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND t.typrelid = 0
  AND t.typtype IN ('d', 'e', 'm', 'r')
  AND pg_get_userbyid(t.typowner) <> 'imperium_admin'
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend d
      WHERE d.classid = 'pg_type'::regclass
        AND d.objid = t.oid
        AND d.deptype = 'e'
  )
ORDER BY n.nspname, t.typname
\gexec

SELECT format(
    CASE p.prokind
        WHEN 'a' THEN 'ALTER AGGREGATE %I.%I(%s) OWNER TO imperium_admin'
        WHEN 'p' THEN 'ALTER PROCEDURE %I.%I(%s) OWNER TO imperium_admin'
        ELSE 'ALTER FUNCTION %I.%I(%s) OWNER TO imperium_admin'
    END,
    n.nspname,
    p.proname,
    pg_get_function_identity_arguments(p.oid)
)
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND p.prokind IN ('a', 'f', 'p', 'w')
  AND pg_get_userbyid(p.proowner) <> 'imperium_admin'
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend d
      WHERE d.classid = 'pg_proc'::regclass
        AND d.objid = p.oid
        AND d.deptype = 'e'
  )
ORDER BY n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)
\gexec

DO $$
DECLARE
    unexpected_owner_count integer;
BEGIN
    SELECT count(*) INTO unexpected_owner_count
    FROM (
        SELECT pg_get_userbyid(n.nspowner) AS owner
        FROM pg_namespace n
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'

        UNION ALL

        SELECT pg_get_userbyid(c.relowner) AS owner
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
          AND NOT EXISTS (
              SELECT 1
              FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass
                AND d.objid = c.oid
                AND d.deptype = 'e'
          )

        UNION ALL

        SELECT pg_get_userbyid(t.typowner) AS owner
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND t.typrelid = 0
          AND t.typtype IN ('d', 'e', 'm', 'r')
          AND NOT EXISTS (
              SELECT 1
              FROM pg_depend d
              WHERE d.classid = 'pg_type'::regclass
                AND d.objid = t.oid
                AND d.deptype = 'e'
          )

        UNION ALL

        SELECT pg_get_userbyid(p.proowner) AS owner
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND p.prokind IN ('a', 'f', 'p', 'w')
          AND NOT EXISTS (
              SELECT 1
              FROM pg_depend d
              WHERE d.classid = 'pg_proc'::regclass
                AND d.objid = p.oid
                AND d.deptype = 'e'
          )
    ) restored_objects
    WHERE restored_objects.owner <> 'imperium_admin';

    IF unexpected_owner_count > 0 THEN
        RAISE EXCEPTION
            'Restored imperium_core objects must be owned by imperium_admin; found % objects owned by another role',
            unexpected_owner_count;
    END IF;
END
$$;

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
