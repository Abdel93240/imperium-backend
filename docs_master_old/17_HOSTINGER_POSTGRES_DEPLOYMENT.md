# 17 - Hostinger PostgreSQL Deployment Checklist

## Purpose

This document defines the checklist for connecting the FastAPI backend to PostgreSQL on the Hostinger VPS.

Do not store VPS credentials in this document.

Do not attempt connection until credentials are provided.

## Target Database

Canonical database name:

```text
imperium_core
```

Database role/user:

```text
TODO
```

Host:

```text
TODO
```

Port:

```text
5432
```

## Required PostgreSQL Extensions

The database must enable:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
```

Purpose:
- `pgcrypto`: UUID/random/security helpers where needed.
- `vector`: pgvector semantic memory extension.

Verification:

```sql
SELECT extname
FROM pg_extension
WHERE extname IN ('pgcrypto', 'vector');
```

Expected result:

```text
pgcrypto
vector
```

## Required `.env` Variables

Backend file:

```text
backend/.env
```

Required variables:

```env
APP_NAME=Personal AI OS API
ENVIRONMENT=production
DEBUG=false
API_V1_PREFIX=/api

DATABASE_URL=postgresql+psycopg://<db_user>:<db_password>@<host>:5432/imperium_core
DATABASE_CONNECT_TIMEOUT_SECONDS=2

JWT_SECRET_KEY=<strong_random_secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=30

INTERNAL_WEBHOOK_SECRET=<strong_random_internal_secret>
WEBHOOK_SIGNATURE_ALGORITHM=HMAC-SHA256
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=60
```

Rules:
- Never use `change-me-before-use`.
- Never commit real `.env` secrets.
- Use URL encoding for special characters in database passwords.
- `DATABASE_URL` must point to `imperium_core`.
- `DEBUG=false` in production.

## How To Test `DATABASE_URL`

From the VPS or local machine with network access:

```powershell
cd C:\Users\BOSS\OneDrive\Bureau\app\backend
.\.venv\Scripts\python.exe -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT 1')).scalar()); c.close()"
```

Expected result:

```text
1
```

Linux/VPS equivalent:

```bash
cd /path/to/backend
./.venv/bin/python -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT 1')).scalar()); c.close()"
```

If this fails, do not run migrations yet.

## How To Run Alembic

After `DATABASE_URL` test succeeds:

```powershell
cd C:\Users\BOSS\OneDrive\Bureau\app\backend
.\.venv\Scripts\alembic.exe upgrade head
```

Linux/VPS equivalent:

```bash
cd /path/to/backend
./.venv/bin/alembic upgrade head
```

Expected result:

```text
Running upgrade  -> 20260425_0001, initial backend skeleton tables
```

Then verify tables:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected V1 skeleton tables:
- `alembic_version`
- `auth_events`
- `devices`
- `events`
- `idempotency_keys`
- `refresh_tokens`
- `users`

## How To Verify `/api/health/db`

Start the API:

```powershell
cd C:\Users\BOSS\OneDrive\Bureau\app\backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

Call:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 10
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health/db" -TimeoutSec 10
```

Expected:

```json
{"status":"ok"}
```

for both endpoints.

Meaning:
- `/api/health` proves FastAPI is alive.
- `/api/health/db` proves PostgreSQL is reachable and responds to `SELECT 1`.

## Common Failure Cases And Fixes

### 1. API fails startup because secret is unchanged

Error:

```text
JWT_SECRET_KEY must be changed before startup.
```

or:

```text
INTERNAL_WEBHOOK_SECRET must be changed before startup.
```

Fix:
- Replace placeholder secrets in `.env`.
- Use strong random values.

### 2. `DATABASE_URL` timeout

Symptoms:
- `alembic upgrade head` hangs or times out.
- `/api/health/db` returns `503`.
- `SELECT 1` connection test times out.

Possible causes:
- Hostinger firewall blocks inbound PostgreSQL.
- PostgreSQL listens only on localhost.
- Wrong host or port.
- VPS security group does not allow the client IP.

Fix:
- Confirm PostgreSQL is running.
- Confirm port `5432`.
- Confirm firewall rules.
- If connecting from outside VPS, allow the client IP or use SSH tunnel.

### 3. Authentication failed

Error:

```text
password authentication failed
```

Fix:
- Verify database user.
- Verify database password.
- URL-encode special password characters in `DATABASE_URL`.
- Confirm user has access to `imperium_core`.

### 4. Database does not exist

Error:

```text
database "imperium_core" does not exist
```

Fix:

```sql
CREATE DATABASE imperium_core;
```

Then rerun connection test.

### 5. Missing `vector` extension

Error:

```text
extension "vector" is not available
```

Fix:
- Install pgvector on the VPS PostgreSQL instance.
- Confirm the PostgreSQL version supports the installed pgvector package.
- Then run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 6. Permission denied creating extension

Error:

```text
permission denied to create extension
```

Fix:
- Run extension creation as PostgreSQL superuser/admin.
- Or grant required privileges according to the VPS PostgreSQL setup.

### 7. Alembic cannot find app settings

Symptoms:
- Import error from `app.core.config`.
- Wrong working directory.

Fix:
- Run Alembic from `backend/`.
- Confirm editable install was run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 8. `DATABASE_URL` password has special characters

Problem:
- Characters like `@`, `:`, `/`, `#`, `%`, `?`, `&` can break the URL.

Fix:
- URL-encode the password.

Example:

```text
@ -> %40
: -> %3A
/ -> %2F
# -> %23
% -> %25
```

### 9. `/api/health` works but `/api/health/db` fails

Meaning:
- FastAPI is alive.
- Database connection is failing.

Fix:
- Test `DATABASE_URL`.
- Check PostgreSQL service.
- Check firewall.
- Check credentials.
- Check database exists.
- Check extension/migration state after connection works.

### 10. Migration partially applied

Symptoms:
- Some tables exist.
- Alembic fails midway.

Fix:
- Inspect `alembic_version`.
- Inspect created tables.
- Do not manually delete production data.
- For empty V1 setup only, it may be safe to drop/recreate the database.
- For non-empty data, create a corrective migration.

## Safe Deployment Order

1. Create PostgreSQL database `imperium_core`.
2. Create database user with strong password.
3. Grant required privileges on `imperium_core`.
4. Install/enable `pgcrypto`.
5. Install/enable `vector`.
6. Create backend `.env` with production secrets.
7. Test `DATABASE_URL` with `SELECT 1`.
8. Run `alembic upgrade head`.
9. Start FastAPI.
10. Check `/api/health`.
11. Check `/api/health/db`.
12. Only then continue with backend feature implementation.

## Do Not Do

Do not:
- put credentials in docs
- commit `.env`
- use default secrets
- run migrations before `DATABASE_URL` works
- expose PostgreSQL publicly without firewall controls
- skip extension verification
- treat `/api/health` as DB health
- continue coding business logic while DB connectivity is unknown
