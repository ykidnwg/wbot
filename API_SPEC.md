# API specification (M0)

Base API path: `/api/v1`. The frontend proxies this through `/api/backend` to keep browser requests same-origin. JSON errors follow FastAPI's validation envelope or the documented `detail` message. API responses never include passwords, sessions, access tokens, provider credentials, or database URLs.

## Health

| Method/path | Auth | Response |
| --- | --- | --- |
| `GET /health/live` | no | `200 {"status":"ok"}` if the process is live. |
| `GET /health/ready` | no | `200 {"status":"ok","database":"ok"}` when a simple DB query works; `503` with `database:"unavailable"` otherwise. |

## Authentication

### `POST /auth/login`

Request: `{ "email": "owner@example.com", "password": "…" }`.

On valid active user: `204 No Content` and an HTTP-only, SameSite Lax `Set-Cookie`. The opaque raw session token is **not** in the response JSON. Invalid credentials return `401 {"detail":"Invalid email or password"}` (same message for absent/inactive users). Requests are rate-limit candidates in M1.

### `GET /auth/me`

Requires valid non-expired, non-revoked session cookie. Returns `200 {"id":"uuid", "email":"…"}` or `401`.

### `POST /auth/logout`

Requires or tolerates absent session. Revokes the stored session if present, clears cookie, returns `204`.

## Dashboard

### `GET /dashboard/summary`

Requires session. In M0 returns an honest empty summary:

```json
{
  "connected_accounts": 0,
  "active_personas": 0,
  "generated_images": 0,
  "pending_approval": 0,
  "scheduled_posts": 0,
  "published_posts": 0,
  "failed_posts": 0,
  "estimated_ai_cost": null,
  "services": {
    "database": "ok",
    "worker": "not_configured",
    "queue": "not_configured",
    "providers": "not_configured"
  }
}
```

`estimated_ai_cost: null` means data is not available, not zero.

## Contract evolution

Future endpoints use `/api/v1`, Pydantic schemas, explicit pagination, ownership authorization, idempotency header/key where needed, and contract tests. Breaking changes require a new version path or an agreed deprecation period.

## Operational settings

All endpoints require a valid session. `GET /settings` returns current typed controls. `PUT /settings/{key}` updates a known value and writes an audit event. Numeric values have server-side bounds; `default_timezone` must be a valid IANA timezone. Kill-switch, budget, concurrency, retry, and rate-limit settings are persisted, but background workers and rate-limit middleware do not consume them yet.

`GET /audit-logs?page=1&page_size=50` returns paginated audit history. `GET /notifications?unread_only=false&limit=50` and `POST /notifications/mark-read` are owner-scoped.

## Personas and bulk onboarding

All routes below require a session and filter by authenticated `owner_id`. Age is checked at 18+ by Pydantic and the database. Approval creates an immutable version snapshot; trying to edit an approved persona returns `409`.

| Method/path | Purpose |
| --- | --- |
| `GET /personas?page=1&page_size=50` | List owned personas. |
| `POST /personas` | Create a draft persona. |
| `GET /personas/{persona_id}` | Read an owned persona; another owner's ID returns `404`. |
| `PUT /personas/{persona_id}` | Replace fields on an owned draft only. |
| `POST /personas/{persona_id}/approve` | Approve a draft and return the immutable version. |
| `GET /personas/{persona_id}/versions` | Read approved version history. |
| `POST /personas/batches` | Persist a resumable batch of 1–100 candidates with user-entered target labels. |
| `GET /personas/batches?page=1&page_size=50` | List owned batches with candidate counts. |
| `GET /personas/batches/{batch_id}` | Resume an owned batch and inspect candidate states. |
| `POST /personas/batches/{batch_id}/approve-selected` | Atomically approve selected draft candidate IDs belonging to that batch and owner. |
| `POST /personas/batches/{batch_id}/candidates/{candidate_id}/regenerate` | Returns `503 NEEDS_CREDENTIALS` and does not change any candidate. |

Batch approval creates a persona and immutable approved version for each selected candidate. Unselected candidates stay unchanged. Candidate regeneration is unavailable until an AI provider is selected and configured.

## Content factory MVP

- `GET /api/v1/content` lists only the authenticated owner's items.
- `POST /api/v1/content/generate-caption` creates a draft using an owned, approved persona. The current provider is `mock/template-v1`, a deterministic local template, not an AI service.
- `POST /api/v1/content/{content_id}/approval` accepts `{"decision":"approved"|"rejected","reason": optional}`. It only accepts items in `draft`, records an immutable event against the current content version, and changes the item status.

No image asset is produced, no asynchronous queue is involved, and draft caption editing/version increments are not yet available. These endpoints do not publish content.
