# Imperium Weekly Review V1 Frontend

Static frontend for the backend-owned Weekly Review conversation.

## Open

Open:

```text
Imperium/frontend/weekly-review/index.html
```

Set:

- API base URL, for example `http://127.0.0.1:8000`
- JWT access token from the existing auth login flow

The token is stored in browser `localStorage` as `imperium_access_token`.

## Backend Contract

The screen calls:

- `GET /api/imperium/weekly-review/current`
- `GET /api/imperium/weekly-review/{session_id}/conversation`
- `POST /api/imperium/weekly-review/{session_id}/answer`
- `POST /api/imperium/weekly-review/{session_id}/draft/approve`
- `POST /api/imperium/weekly-review/{session_id}/draft/reject`
- `POST /api/imperium/weekly-review/{session_id}/draft/request-changes`
- `POST /api/imperium/weekly-review/{session_id}/draft/store`

Buttons are rendered only from backend `conversation.allowed_actions`.

## Safety

- The frontend never invents available actions.
- Every POST sends `Idempotency-Key`.
- `raw_payload` is stripped defensively and never rendered.
- No n8n, AI, database, memory, or pgvector calls are made from this frontend.

## Test

From the repository root:

```powershell
node --test "Imperium/frontend/weekly-review/weekly-review.test.mjs"
```
