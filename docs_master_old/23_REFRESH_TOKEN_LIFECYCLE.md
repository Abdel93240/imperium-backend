# 23 - Refresh Token Lifecycle

## Current V1 Behavior

Refresh tokens use:

```text
token_selector.token_secret
```

Stored database fields:

- `token_selector`: searchable selector
- `token_secret_hash`: Argon2 hash of the secret
- `revoked_at`: revocation timestamp
- `expires_at`: expiry timestamp
- `replaced_by_token_id`: token rotation link

The raw refresh token is never stored.

## Refresh Flow

`POST /api/auth/refresh`

Rules:

- split refresh token into selector and secret
- lookup by `token_selector`
- verify `token_secret` against `token_secret_hash`
- reject revoked tokens
- reject expired tokens
- reject mismatched `device_id`
- reject revoked devices
- create a new refresh token
- revoke the old refresh token
- set `old.replaced_by_token_id = new.id`
- issue a new access token

## Logout Flow

`POST /api/auth/logout`

Rules:

- validate refresh token
- validate device binding
- set `revoked_at`

## Cleanup

Expired refresh tokens can be cleaned with:

```bash
python -m app.cli.cleanup_refresh_tokens
```

The command refuses to run unless `current_database()` is:

```text
imperium_core
```

## Deprecated Column

Column:

```text
refresh_tokens.token_hash
```

Status:

```text
deprecated
```

Reason:

The original Argon2-only design could not efficiently lookup a refresh token because Argon2 hashes are intentionally not searchable.

Why it is not dropped immediately:

- existing deployed databases may still contain rows from the first implementation
- dropping the column is safe only after confirming all active refresh tokens use `token_selector` and `token_secret_hash`

## Migration Plan To Remove token_hash

Preflight:

```sql
SELECT count(*) AS legacy_rows
FROM refresh_tokens
WHERE token_selector IS NULL
   OR token_secret_hash IS NULL;
```

Expected:

```text
0
```

Confirm no code references `token_hash`.

Then a future migration may run:

```sql
ALTER TABLE refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_token_hash_unique;
DROP INDEX IF EXISTS refresh_tokens_token_hash_unique;
ALTER TABLE refresh_tokens DROP COLUMN token_hash;
```

Do not run this until the deployment has completed at least one successful refresh/login cycle with the new selector-based design.
