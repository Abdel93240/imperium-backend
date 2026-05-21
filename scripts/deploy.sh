#!/usr/bin/env bash
set -euo pipefail

IMPERIUM_DIR="/opt/imperium"
BACKEND_DIR="${IMPERIUM_DIR}/backend"
COMPOSE_FILE="${IMPERIUM_DIR}/docker-compose.imperium.yml"
SERVICE="imperium-api"
HEALTH_URL="http://127.0.0.1:8000/api/health"
HEALTH_TIMEOUT=90
SMOKE_RETRIES=5
SMOKE_DELAY=3

log()  { echo "[deploy $(date -u +%H:%M:%S)] $*"; }
fail() { echo "[deploy ERROR] $*" >&2; }

if [[ -f "${IMPERIUM_DIR}/.env" ]]; then
  set -a
  source "${IMPERIUM_DIR}/.env"
  set +a
fi

cd "${BACKEND_DIR}"

PREV_COMMIT="$(git rev-parse HEAD)"
log "Rollback point: ${PREV_COMMIT:0:8}"

log "Fetching latest main..."
git fetch origin main
NEW_COMMIT="$(git rev-parse origin/main)"

if [[ "${PREV_COMMIT}" == "${NEW_COMMIT}" ]]; then
  log "Already up to date. Nothing to deploy."
  exit 0
fi

log "Deploying ${PREV_COMMIT:0:8} -> ${NEW_COMMIT:0:8}"
git reset --hard origin/main

build_and_up() {
  log "Building ${SERVICE}..."
  cd "${IMPERIUM_DIR}"
  docker compose -f "${COMPOSE_FILE}" up -d --build "${SERVICE}"
  cd "${BACKEND_DIR}"
}

wait_for_health() {
  log "Waiting for health (max ${HEALTH_TIMEOUT}s)..."
  local elapsed=0 status
  while (( elapsed < HEALTH_TIMEOUT )); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "${SERVICE}" 2>/dev/null || echo unknown)"
    [[ "${status}" == "healthy" ]] && { log "Healthy after ${elapsed}s."; return 0; }
    [[ "${status}" == "unhealthy" ]] && { fail "Container unhealthy."; return 1; }
    sleep 3; elapsed=$((elapsed + 3))
  done
  fail "Health timeout (last: ${status:-unknown})."; return 1
}

smoke_tests() {
  log "Smoke tests..."
  local i
  for (( i=1; i<=SMOKE_RETRIES; i++ )); do
    curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1 && { log "Smoke OK (${i})"; return 0; }
    log "Smoke retry ${i}/${SMOKE_RETRIES}..."; sleep "${SMOKE_DELAY}"
  done
  fail "Smoke failed."; return 1
}

rollback() {
  fail "FAILED — rolling back to ${PREV_COMMIT:0:8}"
  cd "${BACKEND_DIR}"; git reset --hard "${PREV_COMMIT}"
  cd "${IMPERIUM_DIR}"; docker compose -f "${COMPOSE_FILE}" up -d --build "${SERVICE}"
  if wait_for_health && smoke_tests; then
    log "Rollback OK. Restored ${PREV_COMMIT:0:8}."
  else
    fail "ROLLBACK FAILED — manual intervention needed!"
  fi
  exit 1
}

build_and_up || rollback
wait_for_health || rollback
smoke_tests || rollback

log "Deployment successful: ${NEW_COMMIT:0:8}"
echo "DEPLOY_OK ${NEW_COMMIT}"
