#!/usr/bin/env bash
# Sauvegarde de nuit d'imperium_core (compte de l'API, lecture seule), 14 jours gardés, fichiers privés.
set -euo pipefail
umask 077
DIR=/home/abd/imperium-backups
mkdir -p "$DIR"
set -a; . /opt/imperium-backend/backend/.env; set +a
URL=$(echo "$DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')
pg_dump --format=custom --no-owner --file="$DIR/imperium_core_$(date -u +%Y%m%dT%H%M%SZ).dump" "$URL"
find "$DIR" -name 'imperium_core_2*.dump' -mtime +14 -delete
