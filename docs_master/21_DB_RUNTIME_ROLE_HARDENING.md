# 21 - Database Runtime Role Hardening

## Purpose

Separate database privileges for production operation:

- `imperium_admin`: migration/admin role
- `imperium_user`: runtime API role

This protects append-only tables even if application code is compromised or buggy.

## Migration Risk

Do not revoke privileges from the role used by Alembic migrations.

If `imperium_user` is currently used for both runtime and migrations, create or designate `imperium_admin` first, then run future migrations with `imperium_admin`.

Risk if done incorrectly:

- Alembic migrations may fail.
- app startup may fail if runtime lacks required sequence/table privileges.
- event ingestion may fail if `imperium_user` lacks `INSERT` on `events` or `idempotency_keys`.

## Non-Negotiables

- Apply only to `imperium_core`.
- Do not apply these commands to `n8n_db`.
- Do not grant runtime `UPDATE`, `DELETE`, or `TRUNCATE` on append-only tables.
- Keep `events` and `auth_events` insert-only plus readable for diagnostics.

## Preflight

Run as a PostgreSQL superuser or admin role:

```sql
SELECT current_database();
```

Expected:

```text
imperium_core
```

Stop if the result is:

```text
n8n_db
```

Check current role/table privileges:

```sql
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('events', 'auth_events', 'idempotency_keys', 'refresh_tokens')
ORDER BY table_name, grantee, privilege_type;
```

## Role Separation Proposal

Canonical roles:

```text
imperium_admin
imperium_user
```

Use:

- `imperium_admin` for migrations, schema changes, extension management, emergency repair
- `imperium_user` for FastAPI runtime only

## Safe SQL Commands

Connect to `imperium_core` as a superuser/admin.

VPS psql entry:

```bash
sudo -u postgres psql -d imperium_core
```

Confirm:

```sql
SELECT current_database();
```

Expected:

```text
imperium_core
```

Create the admin role if it does not already exist:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_admin') THEN
        CREATE ROLE imperium_admin LOGIN PASSWORD 'REPLACE_WITH_STRONG_ADMIN_PASSWORD';
    END IF;
END
$$;
```

Ensure runtime role exists:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_user') THEN
        CREATE ROLE imperium_user LOGIN PASSWORD 'REPLACE_WITH_STRONG_RUNTIME_PASSWORD';
    END IF;
END
$$;
```

Allow both roles to connect:

```sql
GRANT CONNECT ON DATABASE imperium_core TO imperium_admin;
GRANT CONNECT ON DATABASE imperium_core TO imperium_user;
```

Schema access:

```sql
GRANT USAGE ON SCHEMA public TO imperium_admin;
GRANT USAGE ON SCHEMA public TO imperium_user;
```

Admin migration privileges:

```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO imperium_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO imperium_admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO imperium_admin;
```

Runtime baseline privileges:

```sql
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO imperium_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO imperium_user;
```

Runtime needs limited updates for non-append-only operational tables:

```sql
GRANT UPDATE ON users TO imperium_user;
GRANT UPDATE ON devices TO imperium_user;
GRANT UPDATE ON refresh_tokens TO imperium_user;
GRANT UPDATE ON idempotency_keys TO imperium_user;
```

Append-only hardening for `events` and `auth_events`:

```sql
REVOKE UPDATE, DELETE, TRUNCATE ON events FROM imperium_user;
REVOKE UPDATE, DELETE, TRUNCATE ON auth_events FROM imperium_user;
GRANT SELECT, INSERT ON events TO imperium_user;
GRANT SELECT, INSERT ON auth_events TO imperium_user;
```

Default privileges for future tables:

```sql
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT ON TABLES TO imperium_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL PRIVILEGES ON TABLES TO imperium_admin;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO imperium_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL PRIVILEGES ON SEQUENCES TO imperium_admin;
```

## Verification

Confirm runtime cannot update append-only tables:

```bash
PGPASSWORD='RUNTIME_PASSWORD' psql \
  --host=31.97.52.42 \
  --username=imperium_user \
  --dbname=imperium_core \
  --command="UPDATE events SET event_type = event_type WHERE false;"
```

Expected:

```text
permission denied
```

or append-only trigger rejection if privileges are broader than expected.

Confirm runtime cannot truncate:

```bash
PGPASSWORD='RUNTIME_PASSWORD' psql \
  --host=31.97.52.42 \
  --username=imperium_user \
  --dbname=imperium_core \
  --command="TRUNCATE events;"
```

Expected:

```text
permission denied
```

or:

```text
TRUNCATE is forbidden
```

Confirm runtime can insert event records through the backend:

```text
POST /api/events
```

Expected:

```text
201 Created
```

Confirm admin can run migrations:

```bash
DATABASE_URL='postgresql+psycopg://imperium_admin:ADMIN_PASSWORD@31.97.52.42:5432/imperium_core' alembic upgrade head
```

## Deployment Decision

After this role split:

- backend runtime `DATABASE_URL` should use `imperium_user`
- Alembic/admin `DATABASE_URL` should use `imperium_admin`

Never use `imperium_admin` as the normal FastAPI runtime role.

## Exact VPS Deployment Steps

1. Create/update roles from a PostgreSQL admin session:

```bash
sudo -u postgres psql -d imperium_core
```

2. Run the role SQL in this document.

3. Create separate secret files:

```bash
cat > /etc/imperium/imperium-db-admin.pass <<'EOF'
REPLACE_WITH_ADMIN_PASSWORD
EOF
chmod 600 /etc/imperium/imperium-db-admin.pass

cat > /etc/imperium/imperium-db-runtime.pass <<'EOF'
REPLACE_WITH_RUNTIME_PASSWORD
EOF
chmod 600 /etc/imperium/imperium-db-runtime.pass
```

4. Use admin URL only for migrations:

```bash
export DATABASE_URL="postgresql+psycopg://imperium_admin:ADMIN_PASSWORD@31.97.52.42:5432/imperium_core"
cd /root/imperium/backend
alembic upgrade head
```

5. Use runtime URL for FastAPI:

```bash
export DATABASE_URL="postgresql+psycopg://imperium_user:RUNTIME_PASSWORD@31.97.52.42:5432/imperium_core"
```

6. Redeploy `imperium-api`.

7. Verify runtime cannot mutate append-only tables:

```bash
PGPASSWORD="$(cat /etc/imperium/imperium-db-runtime.pass)" psql \
  --host=31.97.52.42 \
  --username=imperium_user \
  --dbname=imperium_core \
  --command="UPDATE events SET event_type = event_type WHERE false;"
```

Expected:

```text
permission denied
```

8. Verify app still works:

```text
GET /api/health
GET /api/health/db
POST /api/internal/webhook-test
```

Do not run these steps against `n8n_db`.
