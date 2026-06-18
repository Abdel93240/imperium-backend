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

## Source File Store Scope

Beyond the PostgreSQL database, the backend retains SOURCE FILES on the VPS
filesystem (doc 70 / Knowledge Inbox, PATCH 05): uploaded PDFs, The Path audio,
OCR markdown, etc. These are referenced from the database via
`knowledge_inbox_documents.storage_pointer` but are NOT inside a `pg_dump`.

Rule: the source file store is part of the backup perimeter. A database restore
without its source files yields dead pointers - base and files must be backed up
and restored together.

V1 (decided):
- All source files are backed up from V1, regardless of size. A 30 KB medical OCR
  markdown has no reason to wait for the NAS to be protected.
- Storage location: VPS-local in V1 (abstract pointer, NAS-ready per F06). The
  exact VPS directory layout is the existing Open TODO ("document final VPS
  directory layout") - once fixed, that directory is what gets backed up.
- Same handling as the database dump: encrypt before offsite, same offsite
  location (shared TODO), same daily cadence.

Restore invariant: restore the source file store TOGETHER with the database dump,
never one without the other (consistent with §pgvector Notes: "restore memory only
together with its source structured data").

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

V1 retention (decided - kept deliberately simple to start):

- daily database backups: keep 30 days
- no weekly/monthly tiers in V1.

Rationale: single user, backend not yet run in real conditions. A full
grandfather/father/son scheme (daily + weekly + monthly tiers) is intentionally
DEFERRED. If real usage shows a need to roll back further than 30 days, or volume
makes it worthwhile, promote to the full scheme then - do not pre-engineer it now.

Note: this daily-only policy matches §Backup Frequency, which generates a daily
backup only. (The previous 14d/8w/6m recommendation described weekly/monthly tiers
that nothing ever produced - removed to keep retention and frequency consistent.)

TODO:

- choose final offsite backup location
- choose final backup encryption passphrase storage method
- choose final automated cleanup job (daily, 30-day window)

## Source Retention & Purge (by reference)

This is distinct from backup rotation (above). It governs when a retained SOURCE
file may be deleted from the live store.

Rule - purge by reference, never by fixed age:
- A source file is NEVER purged while ANY entity references it: a project created
  from it (created_entity_id), a vector chunk pointing to it, or a record that may
  re-fetch its exact content (e.g. a medical OCR source).
- A source becomes eligible for purge ONLY when it is fully ORPHANED (no entity,
  no vector, no record points to it) AND the user explicitly confirms deletion.
- Never a silent/automatic deletion of a referenced source. Consistent with the
  project-wide "user is the final decision-maker" rule and doc 70 §4 ("never
  silently overwrite or delete previously ingested knowledge").

VPS -> NAS migration (future, F06):
- When the NAS exists, heavy sources migrate to it; `storage_location` flips
  vps_local -> nas and `storage_pointer` is repointed. No entity/vector change is
  required (indirection F06). Migration must preserve the reference graph above.

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
