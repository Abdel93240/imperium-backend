<!-- hello world -->
# Backend V1 Skeleton

FastAPI backend skeleton for the personal AI operating system.

This is intentionally only the foundation:
- config loading
- database connection
- SQLAlchemy base models
- Alembic setup
- auth/device/event/idempotency tables
- auth and device route skeletons
- health check endpoint
- service package placeholders matching `docs_master/15_SERVICE_ARCHITECTURE_MAP.md`

No full business logic is implemented yet.

## Stack

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- pgvector extension
- UUID primary keys

## Local Setup

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Default local API:

```text
http://localhost:8000
```

## Health Checks

```text
GET /api/health
```

Confirms only that the FastAPI process is alive.

```text
GET /api/health/db
```

Checks PostgreSQL with `SELECT 1`.

## Security Skeleton Notes

- `JWT_SECRET_KEY` must not be `change-me-before-use`.
- `INTERNAL_WEBHOOK_SECRET` must not be `change-me-before-use`.
- App-authenticated requests must derive `user_id` from JWT when auth is implemented.
- Internal n8n requests must use the HMAC/signature path.
- Client-supplied `user_id` must not be trusted blindly.

## First User Bootstrap

The backend does not silently create the canonical user during normal login.

Create the one V1 user explicitly after `alembic upgrade head`:

```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core"
python -m app.cli.create_user
```

The command prompts for:

- email
- password
- master key
- optional device label

Optional bootstrap device, using environment variables:

```powershell
$env:IMPERIUM_BOOTSTRAP_DEVICE_LABEL="Pixel 7 Pro"
$env:IMPERIUM_BOOTSTRAP_DEVICE_PLATFORM="android"
python -m app.cli.create_user
```

Fully non-interactive mode:

```powershell
$env:DATABASE_URL="postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core"
$env:IMPERIUM_BOOTSTRAP_EMAIL="you@example.com"
$env:IMPERIUM_BOOTSTRAP_PASSWORD="REPLACE_WITH_PASSWORD"
$env:IMPERIUM_BOOTSTRAP_MASTER_KEY="REPLACE_WITH_MASTER_KEY"
$env:IMPERIUM_BOOTSTRAP_DEVICE_LABEL="Pixel 7 Pro"
$env:IMPERIUM_BOOTSTRAP_DEVICE_PLATFORM="android"
python -m app.cli.create_user
```

Safety rules enforced by the command:

- refuses to run unless `current_database()` is `imperium_core`
- refuses if a canonical user already exists
- hashes password and master key before storage
- creates `auth_events.event_type = user.bootstrap.created`
- does not print password or master key

## Credential Reset

Use the admin reset CLI if the login password or master key must be rotated:

```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core"
python -m app.cli.reset_credentials
```

Interactive mode prompts for:

- new password, optional
- new master key, optional
- whether to revoke all refresh tokens
- whether to revoke trusted devices except selected IDs
- device IDs to keep trusted, comma-separated and optional

Fully non-interactive mode:

```powershell
$env:DATABASE_URL="postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core"
$env:IMPERIUM_RESET_PASSWORD="REPLACE_WITH_NEW_PASSWORD"
$env:IMPERIUM_RESET_MASTER_KEY="REPLACE_WITH_NEW_MASTER_KEY"
$env:IMPERIUM_RESET_REVOKE_REFRESH_TOKENS="true"
$env:IMPERIUM_RESET_REVOKE_DEVICES="true"
$env:IMPERIUM_RESET_KEEP_DEVICE_IDS="DEVICE_UUID_TO_KEEP,OTHER_DEVICE_UUID_TO_KEEP"
python -m app.cli.reset_credentials
```

Safety rules enforced by the command:

- refuses to run unless `current_database()` is `imperium_core`
- refuses if the canonical user does not exist
- refuses if no reset action is selected
- hashes password and master key before storage
- does not print password or master key
- logs `auth.password.reset` when password is changed
- logs `auth.master_key.reset` when master key is changed
- logs `auth.devices.revoked` when trusted devices are revoked

## Reviewed Future Improvement

Async SQLAlchemy is a reviewed future improvement.

V1 skeleton intentionally stays on synchronous SQLAlchemy until there is a concrete need to switch.
