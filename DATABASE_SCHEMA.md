# Database schema

PostgreSQL is the production database. All timestamps are `timestamptz` in UTC; user-facing schedules also retain an IANA timezone name. UUID primary keys avoid exposing sequential identifiers.

## Implemented by initial migration

### `users`

| Column | Notes |
| --- | --- |
| `id` | UUID primary key |
| `email` | normalized lowercase, unique, non-empty |
| `password_hash` | Argon2id encoded hash; no plaintext |
| `is_active` | blocks authentication when false |
| `created_at`, `updated_at` | UTC timestamps |

### `sessions`

| Column | Notes |
| --- | --- |
| `id` | UUID primary key |
| `user_id` | FK `users.id`, cascades only when the user is deleted |
| `token_hash` | SHA-256 digest of opaque random session token; unique |
| `expires_at`, `revoked_at`, `last_seen_at` | server-side session lifecycle |
| `created_at` | UTC timestamp |

Indexes: `users(email)`, `sessions(token_hash)`, and `sessions(user_id, expires_at)`. The migration has matching constraint names and is safe to run via Alembic's version table repeatedly.

## Planned tables and principal constraints

| Area | Tables | Integrity rules |
| --- | --- | --- |
| Social connection | `social_connections`, `social_targets`, `oauth_states` | owner FK; Facebook platform constraints; one-time expiring OAuth state; encrypted token envelopes never returned; target unique per connection/external ID. |
| Personas | `personas`, `persona_versions`, `persona_batches`, `persona_candidates`, `persona_assignments` | owner FK; adult-age checks; unique immutable approval versions; assignment requires an owned approved persona and active target. |
| Generation/media | `generation_jobs`, `generation_attempts`, `provider_usage`, `media_assets` | status check constraints; attempt sequence unique per job; media metadata/checksum and storage key are owner-scoped; image bytes stay outside PostgreSQL. |
| Content/review | `content_items`, `content_versions`, `approval_events` | content must reference owner/persona/version; publishing eligibility requires latest approval event; append-only approval events. |
| Publishing | `schedules`, `publishing_jobs`, `publishing_attempts`, `publication_reconciliations` | target capability constraint; idempotency key unique per owner/target; only approved content creates a job; `uncertain` requires reconciliation before a new submit. |
| Campaign/analytics | `campaigns`, `campaign_links`, `analytics_snapshots` | user-entered link provenance; snapshots unique per source/entity/metric/period/retrieved version. |
| Operations | `settings`, `notifications`, `audit_logs`, `idempotency_keys` | owner scope; audit log append-only; operational limits evaluated transactionally. |

## Ownership and deletion policy

Every tenant-owned table includes `owner_id` referencing `users.id`, even if it can also be inferred transitively. Service-layer authorization scopes queries by `owner_id`; a raw identifier alone is never authorization. User deletion is postponed to a retention-policy milestone because cascading published-content/audit data could violate operational requirements. Tokens are revoked before an account is deleted.

## Migration rules

1. Never use `create_all` in production. Run `alembic upgrade head` once before serving traffic.
2. A migration is immutable after release; create a new forward migration for corrections.
3. Review downgrade safety. Production downgrade is not automatic when data is irreversible.
4. Add indexes concurrently/with a maintenance plan for large production tables.

## Implemented persona tables

Migration `20261029_0003` creates `personas` and `persona_versions`. Both are owner-scoped; persona and snapshot age checks enforce 18–120, versions are unique per `(persona_id, version_no)`, and profiles store language, personality, audience, clothing style, identity description, caption preferences, provider/model metadata, and prompt version.

Migration `20261030_0004` creates `persona_batches` and `persona_candidates`. Batches are resumable per owner. Candidates carry the user-entered target label and the profile payload; approval validates owner/batch membership, changes only selected candidates, and creates immutable persona versions in the same transaction. Regeneration is unavailable with `NEEDS_CREDENTIALS` and has no side effect. Social target assignment and reference image storage remain planned.

## Implemented content factory tables

Migration `20261030_0005` adds `generation_jobs`, `content_items`, `content_versions`, and `approval_events`. The current caption MVP stores a synchronous mock-template generation as a succeeded job, then stores its resulting draft/version. `approval_events` references the immutable version reviewed. Real provider attempts, usage/cost data, and asynchronous worker state transitions remain outstanding.

Migration `20261101_0006` adds `media_assets`. The current mock image flow stores validated PNGs through local object storage and persists MIME type, size, dimensions, checksum, prompt, and provider/model provenance. Production must replace the local adapter with an authenticated S3-compatible implementation.

Migration `20261101_0007` adds `oauth_states`, `social_connections`, `social_targets`, and
`persona_assignments`. Social tokens are encrypted envelopes; no token column is exposed by
API schemas. Disconnecting marks a connection revoked and cascades managed targets safely.

## Implemented scheduling, publishing, and campaign tables

Migration `20261102_0008` adds the following.

### `content_items.media_asset_id`

Nullable foreign key to `media_assets(id)` with `ON DELETE SET NULL`; indexed. A content item can attach exactly one validated image. Attaching or removing media returns an approved item to `draft` so it must be approved again before scheduling.

### `content_versions.media_asset_id`

Nullable foreign key to `media_assets(id)` with `ON DELETE SET NULL`; indexed. Each immutable version snapshots the attached media alongside the caption, so an approval event refers to the exact text and image reviewed.

### `schedules`

One schedule per content item and social target. Stores `scheduled_for` in UTC, the IANA `timezone` used to interpret a naive request time, `status` (`scheduled`, `cancelled`, `publishing`, `published`, `failed`, `uncertain`), and an owner-scoped unique `idempotency_key`. Indexed by owner, content, target, time, and `(status, scheduled_for)` for due dispatch.

### `publishing_jobs`

Durable queue row for a due schedule or manual job. Stores platform, status (`queued`, `running`, `succeeded`, `failed`, `retry_wait`, `cancelled`, `needs_credentials`, `needs_approval`, `uncertain`), attempt count, external post id/URL, error category/summary, next retry time, and owner-scoped unique idempotency key. Indexed by owner, schedule, content, target, and `(status, next_retry_at)`.

### `publishing_attempts`

Append-only attempt history. Each row stores attempt number, outcome (`succeeded`, `failed`, `rate_limited`, `uncertain`), HTTP status, safe error category/summary, external post id, and timestamps. Unique on `(publishing_job_id, attempt_no)`.

### `campaigns`

Owner-scoped campaign with optional approved persona, name, platform, primary destination, status (`draft`, `active`, `paused`, `ended`, `archived`), and optional start/end times.

### `campaign_links`

Owner-scoped affiliate URL plus a globally unique opaque tracking id, human label, and optional UTM fields. Global uniqueness is required because the public redirect has no owner context. No destination is fetched by the server.

### `campaign_clicks`

Append-only first-party click record with owner id, campaign link id, timestamp, and optional normalized referrer host. Indexed by owner, link, time, and `(link, clicked_at)`.

## State-transition rules

- Content must be `approved` before a schedule is created.
- Creating a schedule sets content to `scheduled`.
- Cancelling a `scheduled` schedule returns content to `approved` unless another active schedule exists.
- A due schedule becomes `publishing`; a job is created exactly once through its idempotency key.
- Job success sets job `succeeded`, schedule `published`, and content `published` only after a provider returns an external post id.
- Auth/credential failures set job `needs_credentials` and return content to `approved`.
- HTTP 5xx or a timeout during a POST is `uncertain`; it is not retried automatically to avoid duplicate posts. A job left `running` by a crashed worker is recovered as `uncertain` after 15 minutes, requiring human verification instead of a blind retry.
