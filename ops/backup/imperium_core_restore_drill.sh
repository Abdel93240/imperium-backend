#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${IMPERIUM_BACKUP_CONFIG:-/etc/imperium/imperium-backup.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

DB_HOST="${IMPERIUM_DB_HOST:-31.97.52.42}"
DB_PORT="${IMPERIUM_DB_PORT:-5432}"
RESTORE_DB="${IMPERIUM_RESTORE_DB:-imperium_restore_drill}"
ADMIN_USER="${IMPERIUM_ADMIN_USER:-imperium_admin}"
ADMIN_PASSWORD_FILE="${IMPERIUM_ADMIN_PASSWORD_FILE:-/etc/imperium/imperium-db-admin.pass}"
RESTORE_USER="${IMPERIUM_RESTORE_USER:-${IMPERIUM_BACKUP_USER:-imperium_user}}"
RESTORE_PASSWORD_FILE="${IMPERIUM_RESTORE_PASSWORD_FILE:-${IMPERIUM_BACKUP_PASSWORD_FILE:-/etc/imperium/imperium-db-backup.pass}}"
BACKUP_DIR="${IMPERIUM_BACKUP_DIR:-/var/backups/imperium/postgres}"
GPG_PASSPHRASE_FILE="${IMPERIUM_BACKUP_GPG_PASSPHRASE_FILE:-/etc/imperium/imperium-backup-gpg.pass}"
KEEP_DRILL_DB="${KEEP_DRILL_DB:-${IMPERIUM_RESTORE_KEEP_DB:-false}}"

BACKUP_PATH="${1:-}"
if [[ -z "$BACKUP_PATH" ]]; then
  BACKUP_PATH="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "imperium_core_*.dump.gpg" | sort | tail -n 1)"
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_file() {
  [[ -f "$1" ]] || {
    echo "Missing required file: $1" >&2
    exit 1
  }
}

require_command createdb
require_command dropdb
require_command pg_restore
require_command psql
require_command gpg
require_file "$ADMIN_PASSWORD_FILE"
require_file "$RESTORE_PASSWORD_FILE"
require_file "$GPG_PASSPHRASE_FILE"
require_file "$BACKUP_PATH"

umask 077

if [[ "$RESTORE_DB" == "imperium_core" || "$RESTORE_DB" == "n8n_db" || "$RESTORE_DB" != "imperium_restore_drill" ]]; then
  echo "Refusing unsafe restore database name: $RESTORE_DB" >&2
  exit 1
fi

TMP_DUMP="$(mktemp "/tmp/${RESTORE_DB}.XXXXXX.dump")"
TMP_LIST="$(mktemp "/tmp/${RESTORE_DB}.XXXXXX.list")"

run_admin() {
  PGPASSWORD="$(<"$ADMIN_PASSWORD_FILE")" "$@"
}

run_restore_user() {
  PGPASSWORD="$(<"$RESTORE_PASSWORD_FILE")" "$@"
}

cleanup() {
  if [[ -f "$TMP_DUMP" ]]; then
    if command -v shred >/dev/null 2>&1; then
      shred -u "$TMP_DUMP"
    else
      rm -f "$TMP_DUMP"
    fi
  fi

  rm -f "$TMP_LIST"

  if [[ "${KEEP_DRILL_DB,,}" != "true" ]]; then
    run_admin dropdb \
      --if-exists \
      --host="$DB_HOST" \
      --port="$DB_PORT" \
      --username="$ADMIN_USER" \
      "$RESTORE_DB" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

gpg \
  --batch \
  --yes \
  --pinentry-mode loopback \
  --decrypt \
  --passphrase-file "$GPG_PASSPHRASE_FILE" \
  --output "$TMP_DUMP" \
  "$BACKUP_PATH"

run_admin dropdb \
  --if-exists \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$ADMIN_USER" \
  "$RESTORE_DB"

run_admin createdb \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$ADMIN_USER" \
  --owner="$RESTORE_USER" \
  "$RESTORE_DB"

run_admin psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$ADMIN_USER" \
  --dbname="$RESTORE_DB" \
  --command="CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;"

pg_restore --list "$TMP_DUMP" \
  | grep -Ev ' EXTENSION (pgcrypto|vector)( |$)| COMMENT - EXTENSION (pgcrypto|vector)( |$)' \
  > "$TMP_LIST"

run_restore_user pg_restore \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$RESTORE_USER" \
  --dbname="$RESTORE_DB" \
  --no-owner \
  --no-acl \
  --use-list="$TMP_LIST" \
  "$TMP_DUMP"

CURRENT_DB="$(
  run_restore_user psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$RESTORE_USER" \
    --dbname="$RESTORE_DB" \
    --tuples-only \
    --no-align \
    --command="SELECT current_database();"
)"

if [[ "$CURRENT_DB" != "$RESTORE_DB" ]]; then
  echo "Restore drill connected to unexpected database '$CURRENT_DB'." >&2
  exit 1
fi

run_restore_user psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$RESTORE_USER" \
  --dbname="$RESTORE_DB" \
  --no-align \
  --tuples-only \
  --command="
    SELECT 'users_singleton=' || count(*) FROM users WHERE single_user_mode IS TRUE;
    SELECT 'events=' || count(*) FROM events;
    SELECT 'auth_events=' || count(*) FROM auth_events;
    SELECT 'alembic_version=' || version_num FROM alembic_version;
  "

echo "Restore drill succeeded against sandbox database: $RESTORE_DB"
if [[ "${KEEP_DRILL_DB,,}" == "true" ]]; then
  echo "Sandbox database kept because KEEP_DRILL_DB=true"
else
  echo "Sandbox database will be dropped by cleanup."
fi
