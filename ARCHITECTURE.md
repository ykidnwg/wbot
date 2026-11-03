# Architecture

## M0 system context

```text
Browser
  | HTTPS / same origin
  v
Next.js frontend (:3000) -- internal proxy --> FastAPI (:8000)
                                                   |        |
                                                   v        v
                                           PostgreSQL (:5432) Redis (:6379)
                                           persistent data     broker/cache (M2+)
```

Only frontend is published by the development Compose file. PostgreSQL and Redis have no host port mappings. Production adds Caddy on ports 80/443 in front of the frontend, with TLS certificates managed outside source control.

## Boundaries

- `frontend/`: browser UI. It cannot read database credentials or provider secrets. API traffic is same-origin (`/api/backend/*`) and proxied server-side by Next.js.
- `backend/app/api`: HTTP validation, auth dependencies, and schemas only.
- `backend/app/services`: use cases and ports; future providers/adapters live behind interfaces here.
- `backend/app/models`: SQLAlchemy persistence models.
- `backend/alembic`: forward-only migration history.
- Future worker/scheduler containers run the same backend image but consume explicit task types. They persist all status transitions before acknowledging work.

## Security baseline in M0

- Passwords are Argon2id hashes through `pwdlib`; plaintext passwords are never logged or stored.
- A successful login creates an opaque random session. Only its SHA-256 digest is stored. The raw value exists only in an HTTP-only, `SameSite=Lax` cookie.
- `SESSION_COOKIE_SECURE=true` is mandatory for HTTPS production and defaults false only for local HTTP.
- CORS is allow-listed from environment; the browser UI normally uses the proxy so it need not receive cross-origin credentials.
- Configuration rejects unexpected fields and rejects insecure cookie mode outside development/test.
- Every future query must include ownership predicates. Database foreign keys and compound unique constraints reinforce application authorization but do not replace it.
- M0 has no upload, external URL fetch, token storage, social credential, generation, worker, or publishing endpoint.

## Future domain flow

```text
Persona version -> candidate batch -> generation job -> media asset -> content item
                                                               -> approval event
approved content + schedule -> publishing job -> adapter -> external result/reconciliation
                                                         -> analytics snapshot
```

Each arrow is an explicit persisted transition with an audit log. A provider adapter returns a typed success or categorized failure; it must never simulate an external success. Jobs distinguish validation/auth/permission/quota/moderation/rate-limit/temporary/network/unknown outcomes. Only temporary/rate-limit failures are retryable, using bounded exponential backoff with jitter.

## External integrations (not implemented in M0)

Before M5/M7, a maintainer must reread and cite the exact current official documentation:

- Meta Graph API: <https://developers.facebook.com/docs/graph-api/>
- Facebook Pages: <https://developers.facebook.com/docs/pages-api/>
- Instagram Platform: <https://developers.facebook.com/docs/instagram-platform/>
- Threads API: <https://developers.facebook.com/docs/threads/>
- X API: <https://developer.x.com/en/docs/x-api>

The provider decision for images/captions is intentionally deferred; a provider is not selected, and no undocumented endpoint/model is assumed.

## Deployment posture

Settings updates are authenticated, type/range validated, and audited. The current settings UI stores kill-switch, budgets, concurrency, retries, time zone, and rate-limit values; workers and rate-limit enforcement are not active yet.

Persona draft and batch operations always scope reads by `owner_id`. Approving a draft snapshots it into `persona_versions`; the API does not expose mutation of an approved snapshot. Bulk approval locks and checks candidate IDs for the current owner and batch before creating persona/version rows. A regenerate request reports `NEEDS_CREDENTIALS` without changing data.

## Content factory MVP

`CaptionProvider` is a typed backend boundary. `MockCaptionProvider` generates a deterministic local template and stores provider/model provenance on the generation job and content version. The content API requires an owner-scoped approved persona, creates a draft, and requires an explicit approval decision. Review history is immutable and binds to the exact content version. The current request is synchronous; no worker, image provider, external model, upload, or publishing API is configured.

The image boundary now has a typed `ImageProvider` and deterministic `MockImageProvider`. Generated PNG bytes are validated for MIME type, size, dimensions, CRCs, and decompression integrity before being written through an object-storage-shaped local adapter. PostgreSQL stores only owner-scoped metadata, checksum, provider/model provenance, and storage key. The live provider boundary remains unconfigured; reference-image identity is not promised.

The social boundary uses a generic Meta adapter contract with a Facebook implementation.
OAuth state is short-lived, hashed, owner-scoped, and one-time consumed. Connections and
Pages are owner-scoped; tokens are encrypted with AES-GCM. Persona assignments reference
only approved personas and active social targets. The current milestone discovers Pages but
does not publish content.

Development uses `docker compose up --build`. Production will use a separate override and Caddy configuration after domain, storage, backup target, and credentials are supplied. PostgreSQL/Redis stay on the private Compose network; credentials come from a secret manager or deployment environment, not `compose.yml`. Backups, restore verification, image pruning, and rollback procedure are documented before M8 approval.
