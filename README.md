# AI Social Automation Platform

Owner-scoped content operations for fictional adult personas. The repository now includes a complete planning loop: role-free single-owner sessions, adult persona drafts with immutable approval versions, resumable bulk onboarding, caption and image generation through configurable providers, validated media storage, a durable calendar and publishing queue, a database-backed worker, Facebook Page publishing through the Graph API, campaigns with first-party tracked links, and analytics derived only from owned records.

Mock providers remain the default. A live OpenAI-compatible caption/image provider and the Meta Graph publisher are used only after server-side credentials are configured; otherwise the UI/API returns an honest `NEEDS_CREDENTIALS` state. No external metric, cost, reach, or revenue value is invented.

## Run locally with Docker

Requirements: Docker Engine and Docker Compose v2.

1. Copy `.env.example` to `.env`.
2. Set a private PostgreSQL password consistently in `POSTGRES_PASSWORD`, `DATABASE_URL`, and `DATABASE_URL_SYNC`. Set `INITIAL_ADMIN_EMAIL` to a valid email address and a long `INITIAL_ADMIN_PASSWORD` for the local administrator. These values stay in the ignored `.env`; never commit them.
3. Optionally set `OPENAI_API_KEY` for live caption/image generation, and `META_APP_ID`, `META_APP_SECRET`, `META_OAUTH_REDIRECT_URI`, and `TOKEN_ENCRYPTION_KEY` for Facebook OAuth and publishing. Leave them unset to keep explicit `NEEDS_CREDENTIALS` behavior.
4. Run `docker compose up --build -d` from the repository root. Compose waits for PostgreSQL and Redis, applies Alembic migrations, starts the API, the worker, and the web app.
5. Open <http://localhost:3000> and sign in with the administrator configured above.

Useful checks:

```powershell
docker compose ps
docker compose logs --tail=50 backend worker
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

## What is implemented

- **Personas:** age-gated adult drafts, immutable approval snapshots, editable draft versions, and resumable batch onboarding.
- **Content:** versioned caption drafts, explicit approval, optional media attachment, and an immutable approval event history.
- **Providers:** deterministic mock caption/image providers plus an OpenAI-compatible chat-completions/image API adapter selected through settings. Credentials stay in server environment variables.
- **Media:** validated PNG/JPEG/WebP bytes, checksums, dimensions, owner-scoped previews, and a storage boundary suitable for an S3-compatible adapter.
- **Calendar and publishing:** one schedule per content/target pair, idempotent creation, cancellation, a database-backed worker, category-aware retries, `needs_credentials`, and `uncertain` outcomes that are never retried automatically.
- **Facebook:** OAuth with hashed one-time state, encrypted Page tokens, Page discovery, persona assignment, and Graph API publishing of text or image posts. Tests use fakes and make no external calls.
- **Campaigns and analytics:** affiliate destinations, generated tracking paths, first-party click recording, and owner-scoped campaign/link/content/publishing metrics.

## Security and data boundaries

- Session tokens are random, stored hashed in PostgreSQL, and sent only in HTTP-only cookies. Production requires `APP_ENV=production` and `SESSION_COOKIE_SECURE=true` behind HTTPS.
- Admin bootstrap is optional and reads only private environment variables. There is no public registration/reset flow yet.
- Do not add social passwords, API keys, tokens, or other credentials to source, logs, images, or API responses.
- Only official social APIs may be used. No scraping or browser login automation is part of this project.
- Provider and platform integration status remains `not_configured` / `NEEDS_CREDENTIALS` until its official contract, credentials, and tests exist.
- Page access tokens are encrypted with AES-GCM. Provider API keys and token-encryption keys are server-only.
- The tracked-link redirect only follows stored HTTP(S) URLs, rejects embedded credentials, and records clicks without external tracking scripts.
- All counts on the dashboard and analytics page come from owned database records. External metrics, AI cost, and revenue are shown unavailable rather than estimated.

## Testing

Docker image builds run the full checks before producing runtime images:

- Backend: `ruff check app tests`, `mypy app`, `pytest`.
- Frontend: `npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build`.

Host development requires Python 3.14 and Node.js 22 with npm 10. Install backend dependencies with `python -m pip install -e ".[dev]"` from `backend`, and frontend dependencies with `npm ci` from `frontend`.

Tests never call paid AI or Meta endpoints. Live-provider paths are covered with deterministic fakes and missing-credential tests.

## Deployment status

Docker Compose is a local foundation, not yet a VPS-ready public deployment. Caddy/Nginx TLS, production Compose overrides, backup/restore automation, monitoring, distributed rate limiting, and a deployment rollback procedure remain part of production hardening. See [PROJECT_PLAN.md](PROJECT_PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), [API_SPEC.md](API_SPEC.md), [TEST_PLAN.md](TEST_PLAN.md), and [PROGRESS.md](PROGRESS.md).
