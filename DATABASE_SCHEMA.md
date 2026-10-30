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
| Social connection | `connected_accounts`, `social_targets` | owner FK; platform enum; encrypted token envelope never returned; target unique per connected account/external ID. |
| Personas | `personas`, `persona_versions`, `persona_batches`, `persona_candidates` implemented; `persona_assignments` planned | owner FK; adult-age checks; unique immutable approval versions; batch selections must match the owner and batch. |
| Generation/media | `generation_jobs`, `generation_attempts`, `provider_usage`, `media_assets` | status check constraints; attempt sequence unique per job; media checksum unique within owner; provider cost nullable unless supplied by provider. |
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

Migration `20261030_0005` adds `generation_jobs`, `content_items`, `content_versions`, and `approval_events`. The current caption MVP stores a synchronous mock-template generation as a succeeded job, then stores its resulting draft/version. `approval_events` references the immutable version reviewed. Real provider attempts, usage/cost data, image media assets, and asynchronous worker state transitions remain outstanding.
