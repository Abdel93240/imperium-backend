#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${IMPERIUM_BACKUP_CONFIG:-/etc/imperium/imperium-backup.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

DB_HOST="${IMPERIUM_DB_HOST:-31.97.52.42}"
DB_PORT="${IMPERIUM_DB_PORT:-5432}"
DB_NAME="${IMPERIUM_DB_NAME:-imperium_core}"
DB_USER="${IMPERIUM_BACKUP_USER:-imperium_admin}"
PASSWORD_FILE="${IMPERIUM_BACKUP_PASSWORD_FILE:-/etc/imperium/imperium-db-backup.pass}"
BACKUP_DIR="${IMPERIUM_BACKUP_DIR:-/var/backups/imperium/postgres}"
RETENTION_DAYS="${IMPERIUM_BACKUP_RETENTION_DAYS:-14}"
GPG_PASSPHRASE_FILE="${IMPERIUM_BACKUP_GPG_PASSPHRASE_FILE:-/etc/imperium/imperium-backup-gpg.pass}"
OFFHOST_SYNC_COMMAND="${IMPERIUM_OFFHOST_SYNC_COMMAND:-}"

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

if [[ "$DB_NAME" != "imperium_core" ]]; then
  echo "Refusing to back up database '$DB_NAME'. Expected 'imperium_core'." >&2
  exit 1
fi

require_command pg_dump
require_command psql
require_command gpg
require_command sha256sum
require_file "$PASSWORD_FILE"
require_file "$GPG_PASSPHRASE_FILE"

umask 077
mkdir -p "$BACKUP_DIR"

export PGPASSWORD
PGPASSWORD="$(<"$PASSWORD_FILE")"

CURRENT_DB="$(
  psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --tuples-only \
    --no-align \
    --command="SELECT current_database();"
)"

if [[ "$CURRENT_DB" != "imperium_core" ]]; then
  echo "Refusing backup. Connected to '$CURRENT_DB', expected 'imperium_core'." >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE_NAME="imperium_core_${STAMP}"
DUMP_PATH="${BACKUP_DIR}/${BASE_NAME}.dump"
ENCRYPTED_PATH="${DUMP_PATH}.gpg"
SHA_PATH="${ENCRYPTED_PATH}.sha256"

pg_dump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="$DUMP_PATH"

gpg \
  --batch \
  --yes \
  --pinentry-mode loopback \
  --symmetric \
  --cipher-algo AES256 \
  --passphrase-file "$GPG_PASSPHRASE_FILE" \
  --output "$ENCRYPTED_PATH" \
  "$DUMP_PATH"

if command -v shred >/dev/null 2>&1; then
  shred -u "$DUMP_PATH"
else
  rm -f "$DUMP_PATH"
fi

sha256sum "$ENCRYPTED_PATH" > "$SHA_PATH"

find "$BACKUP_DIR" \
  -type f \
  \( -name "imperium_core_*.dump.gpg" -o -name "imperium_core_*.dump.gpg.sha256" \) \
  -mtime "+${RETENTION_DAYS}" \
  -print \
  -delete

if [[ -n "$OFFHOST_SYNC_COMMAND" ]]; then
  IMPERIUM_LATEST_BACKUP="$ENCRYPTED_PATH" \
  IMPERIUM_LATEST_BACKUP_SHA256="$SHA_PATH" \
  bash -c "$OFFHOST_SYNC_COMMAND"
fi

unset PGPASSWORD

echo "Backup created: $ENCRYPTED_PATH"
echo "Checksum: $SHA_PATH"
