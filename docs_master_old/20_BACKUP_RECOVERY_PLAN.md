# 20 - Backup and Recovery Operational Plan

## Purpose

Define the V1 operational backup and recovery plan for the personal AI OS backend.

Executable scripts and VPS install commands are defined in:

```text
docs_master/22_BACKUP_EXECUTION_LAYER.md
```

This plan protects:

- PostgreSQL canonical truth
- authentication records
- append-only events
- idempotency state
- future pgvector memory
- deployment configuration

## Non-Negotiables

- Back up `imperium_core`, not `n8n_db`.
- Do not run Imperium backend migrations against `n8n_db`.
- Backups must be encrypted.
- Secrets must not be committed to the repository.
- Restore tests are required; an untested backup is not trusted.
- Events and auth events are append-only operational records.

## Database Scope

Primary database:

```text
imperium_core
```

Excluded database:

```text
n8n_db
```

The n8n database may have its own backup process, but it is not the canonical app backend database.

## Backup Command

Run on the VPS or a trusted admin machine with PostgreSQL client tools installed:

```bash
export PGPASSWORD='REPLACE_WITH_IMPERIUM_DB_PASSWORD'
pg_dump \
  --host=31.97.52.42 \
  --port=5432 \
  --username=imperium_user \
  --dbname=imperium_core \
  --format=custom \
  --no-owner \
  --file=imperium_core_$(date -u +%Y%m%dT%H%M%SZ).dump
```

Encrypt immediately:

```bash
gpg --symmetric --cipher-algo AES256 imperium_core_YYYYMMDDTHHMMSSZ.dump
shred -u imperium_core_YYYYMMDDTHHMMSSZ.dump
```

The remaining file should be:

```text
imperium_core_YYYYMMDDTHHMMSSZ.dump.gpg
```

## Backup Frequency

V1 minimum:

- daily encrypted database backup
- weekly restore test
- before every production migration
- before credential reset operations
- before deployment changes that affect database schema

## Retention

Recommended V1 retention:

- daily backups: keep 14 days
- weekly backups: keep 8 weeks
- monthly backups: keep 6 months

TODO:

- choose final offsite backup location
- choose final backup encryption passphrase storage method
- choose final automated cleanup job

## Restore Test

Never restore directly into production first.

Create a temporary restore database:

```bash
createdb imperium_core_restore_test
```

Restore:

```bash
gpg --decrypt imperium_core_YYYYMMDDTHHMMSSZ.dump.gpg > restore_test.dump
pg_restore \
  --host=31.97.52.42 \
  --port=5432 \
  --username=imperium_user \
  --dbname=imperium_core_restore_test \
  --clean \
  --if-exists \
  restore_test.dump
shred -u restore_test.dump
```

Verify:

```sql
SELECT current_database();
SELECT count(*) FROM users WHERE single_user_mode IS TRUE;
SELECT count(*) FROM events;
SELECT count(*) FROM auth_events;
SELECT version_num FROM alembic_version;
```

Expected:

- database is `imperium_core_restore_test`
- one canonical user
- events readable
- auth events readable
- Alembic version present

Drop test database after validation:

```bash
dropdb imperium_core_restore_test
```

## Recovery Procedure

Only use this for a real recovery.

1. Stop `imperium-api`.
2. Confirm the target database name.
3. Back up the broken state before changing it.
4. Restore the encrypted backup to a temporary database first.
5. Verify the temporary restore.
6. Point backend to the restored DB or replace production only after explicit approval.
7. Start `imperium-api`.
8. Verify:

```text
GET /api/health
GET /api/health/db
```

9. Run a login smoke test.
10. Run an internal webhook smoke test.

## Secret Rotation

Rotate `INTERNAL_WEBHOOK_SECRET` after temporary debug endpoints have been removed.

Steps:

1. Generate a new secret of at least 32 characters.
2. Update `backend/.env` on the VPS:

```env
INTERNAL_WEBHOOK_SECRET=REPLACE_WITH_NEW_LONG_SECRET
```

3. Update the n8n environment variable with the same value.
4. Restart `imperium-api`.
5. Restart n8n only if its environment variables require restart.
6. Run the smoke test:

```text
POST /api/internal/webhook-test
```

7. Confirm old signatures fail.

Do not print the secret in logs or chat.

## Deployment Config Backup

Back up separately:

- `backend/.env`
- Docker Compose file
- reverse proxy config if added later
- n8n environment variable source

Do not store these unencrypted.

## pgvector Notes

For V1 skeleton, pgvector is enabled but memory tables are not yet implemented.

When `ai_memories` exists:

- include it in the normal PostgreSQL backup
- remember memory is not canonical truth
- restore memory only together with its source structured data when possible

## Open TODOs

- TODO: choose offsite encrypted storage location
- TODO: automate daily backups
- TODO: automate restore test reporting
- TODO: document final VPS directory layout after deployment is stable
