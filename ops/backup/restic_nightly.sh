#!/usr/bin/env bash
# system.backup_nightly (04:00, job runner seedé désactivé — activation doc 76).
# restic : pg_dump + repo + docs + configs → disque USB dédié + cible distante SSH.
# Dépôt chiffré, rétention 30 j. Le drill de restauration mensuel reste un acte utilisateur.
#
# Config attendue dans /etc/imperium/backup.env :
#   RESTIC_REPOSITORY_USB    ex: /mnt/imperium-backup/restic
#   RESTIC_REPOSITORY_REMOTE ex: sftp:backup@vps-hostinger:/srv/imperium-restic
#   RESTIC_PASSWORD_FILE     ex: /etc/imperium/restic.pass
#   PGDUMP_URL               ex: postgresql://imperium_admin:...@127.0.0.1:5432/imperium_core
set -euo pipefail

ENV_FILE=/etc/imperium/backup.env
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"

: "${RESTIC_REPOSITORY_USB:?RESTIC_REPOSITORY_USB manquant}"
: "${RESTIC_PASSWORD_FILE:?RESTIC_PASSWORD_FILE manquant}"
: "${PGDUMP_URL:?PGDUMP_URL manquant}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
WORKDIR=$(mktemp -d /tmp/imperium-backup.XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT

echo "[backup] pg_dump → $WORKDIR"
pg_dump --format=custom --file="$WORKDIR/imperium_core_$STAMP.dump" "$PGDUMP_URL"

BACKUP_PATHS=(
  "$WORKDIR"
  /opt/imperium-backend/docs_master
  /opt/imperium-backend/ops
  /opt/imperium-backend/backend/.env
  /etc/imperium
)

run_restic() {
  local repo="$1"
  export RESTIC_REPOSITORY="$repo" RESTIC_PASSWORD_FILE
  restic snapshots >/dev/null 2>&1 || restic init
  restic backup "${BACKUP_PATHS[@]}" --tag nightly --tag "socle-v1"
  restic forget --keep-within 30d --prune
}

echo "[backup] cible USB: $RESTIC_REPOSITORY_USB"
run_restic "$RESTIC_REPOSITORY_USB"

if [[ -n "${RESTIC_REPOSITORY_REMOTE:-}" ]]; then
  echo "[backup] cible distante: $RESTIC_REPOSITORY_REMOTE"
  run_restic "$RESTIC_REPOSITORY_REMOTE"
else
  echo "[backup] AVERTISSEMENT: pas de cible distante configurée (VPS gelé attendu)" >&2
fi

echo "[backup] OK $STAMP"
