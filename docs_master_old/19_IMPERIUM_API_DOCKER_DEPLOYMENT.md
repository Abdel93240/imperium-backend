# 19 - Imperium API Docker Deployment

## Purpose

Prepare the `imperium-api` FastAPI backend to run on the Hostinger VPS beside n8n.

This document is deployment preparation only.
Do not modify existing n8n containers during preparation.

## Target Service

Service name:

```text
imperium-api
```

Container internal port:

```text
8000
```

n8n smoke test URL:

```text
http://imperium-api:8000/api/internal/webhook-test
```

## Files

Created deployment files:

```text
backend/Dockerfile
backend/.dockerignore
docker-compose.imperium.yml
```

## Database Rule

The backend must use:

```text
imperium_core
```

It must not use:

```text
n8n_db
```

Required deployment environment value:

```env
DATABASE_URL=postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core
```

Before deployment, verify in the shell that will run Docker Compose:

```bash
printf '%s\n' "$DATABASE_URL"
```

The value must end with:

```text
/imperium_core
```

## Required Deployment Environment Values

Production secrets must not live in the repository.

Do not create or upload:

```text
backend/.env
```

for production deployment.

The Docker Compose file reads required values from the deployment environment.

Set these in the VPS shell, systemd environment file outside the repo, or a protected secret manager:

```env
APP_NAME=Personal AI OS API
ENVIRONMENT=production
DEBUG=false
API_V1_PREFIX=/api

DATABASE_URL=postgresql+psycopg://imperium_user:REPLACE_WITH_STRONG_PASSWORD@31.97.52.42:5432/imperium_core
DATABASE_CONNECT_TIMEOUT_SECONDS=5

JWT_SECRET_KEY=REPLACE_WITH_PRODUCTION_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=30

INTERNAL_WEBHOOK_SECRET=REPLACE_WITH_INTERNAL_WEBHOOK_SECRET
WEBHOOK_SIGNATURE_ALGORITHM=HMAC-SHA256
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=60
```

Do not use placeholder-like values containing:

```text
change-me
replace
placeholder
example
sample
dummy
your_
your-
todo
test
```

for production secrets. The backend refuses startup if these fragments are detected.

## Docker Network

The `imperium-api` container must join the same Docker network as n8n.

Find the current n8n network on the VPS:

```bash
docker ps --format 'table {{.Names}}\t{{.Networks}}'
```

or:

```bash
docker inspect <N8N_CONTAINER_NAME> --format '{{json .NetworkSettings.Networks}}'
```

The compose file uses:

```yaml
networks:
  imperium-internal:
    name: ${IMPERIUM_DOCKER_NETWORK:-n8n-postgresql_default}
    external: true
```

If the n8n network is not `n8n-postgresql_default`, set:

```bash
export IMPERIUM_DOCKER_NETWORK=<ACTUAL_N8N_NETWORK_NAME>
```

before running Docker Compose.

## Docker Compose File

Use:

```text
docker-compose.imperium.yml
```

The service:

- is named `imperium-api`
- builds from `backend/Dockerfile`
- loads required values from the deployment environment
- exposes internal port `8000`
- does not publish port `8000` publicly
- joins the existing n8n Docker network
- healthchecks `GET /api/health`

## Deployment Commands

Do not run until ready.

From the project root on the VPS:

```bash
cd /home/n8n-postgresql/
```

Verify the DB target:

```bash
printf '%s\n' "$DATABASE_URL"
```

Expected:

```text
postgresql+psycopg://imperium_user:...@31.97.52.42:5432/imperium_core
```

Build only:

```bash
docker compose -f docker-compose.imperium.yml build imperium-api
```

Start only the backend service:

```bash
docker compose -f docker-compose.imperium.yml up -d imperium-api
```

Check status:

```bash
docker ps --filter name=imperium-api
```

Check logs:

```bash
docker logs imperium-api --tail 100
```

Check health inside the container:

```bash
docker exec imperium-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read().decode())"
```

Expected:

```json
{"status":"ok"}
```

Check database health inside the container:

```bash
docker exec imperium-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health/db', timeout=10).read().decode())"
```

Expected:

```json
{"status":"ok"}
```

## n8n HTTP Request URL

If n8n and `imperium-api` are on the same Docker network, n8n must call:

```text
http://imperium-api:8000/api/internal/webhook-test
```

Do not use from inside n8n:

```text
localhost
127.0.0.1
```

Those point to the n8n container itself, not to the backend container.

## n8n Smoke Test Headers

The n8n HTTP Request node must send:

```text
X-Timestamp
X-Signature
Idempotency-Key
Content-Type: application/json
```

Signature:

```text
HMAC-SHA256 over {timestamp}.{raw_body}
```

Internal webhooks are authenticated by HMAC signature only. Do not send the shared secret as a header.

See:

```text
docs_master/18_N8N_SMOKE_TEST.md
```

## Expected Smoke Test Response

```json
{
  "status": "ok",
  "accepted": true,
  "idempotency_key": "n8n_smoke_..."
}
```

Expected HTTP status:

```text
200 OK
```

## Common Deployment Issues

### External Network Not Found

Error:

```text
network n8n-postgresql_default declared as external, but could not be found
```

Fix:

Find the real n8n network:

```bash
docker ps --format 'table {{.Names}}\t{{.Networks}}'
```

Then run:

```bash
export IMPERIUM_DOCKER_NETWORK=<ACTUAL_N8N_NETWORK_NAME>
docker compose -f docker-compose.imperium.yml up -d imperium-api
```

### Backend Starts Then Exits

Likely causes:

- `JWT_SECRET_KEY` missing, too short, or placeholder-like
- `INTERNAL_WEBHOOK_SECRET` missing, too short, or placeholder-like
- invalid `DATABASE_URL`
- `imperium_core` unreachable

Check:

```bash
docker logs imperium-api --tail 100
```

### DB Health Fails

Check:

```bash
docker exec imperium-api python -c "import os; print(os.environ['DATABASE_URL'].split('/')[-1])"
```

Expected:

```text
imperium_core
```

If it prints `n8n_db`, stop and fix `backend/.env`.

### n8n Cannot Reach Backend

From inside n8n container:

```bash
docker exec <N8N_CONTAINER_NAME> wget -qO- http://imperium-api:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

If it fails:

- `imperium-api` is not on the same Docker network
- service name is wrong
- backend container is unhealthy
- Docker DNS has not attached the service to the expected network

## Non-Negotiables

- Do not run backend migrations against `n8n_db`.
- Do not point `DATABASE_URL` to `n8n_db`.
- Do not store production secrets in `backend/.env` inside the repository.
- Do not publish backend port `8000` publicly unless there is an explicit reverse-proxy/security decision.
- n8n must call backend APIs, not PostgreSQL directly.
- This deployment adds `imperium-api`; it must not modify existing n8n containers.
