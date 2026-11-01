# AI Social Automation Platform

Runnable SaaS foundation for managing social content workflows. The current implementation includes PostgreSQL-backed user sessions, operational settings, audit logs, notifications, health checks, adult persona drafts, immutable approval versions, and resumable bulk persona batches. Social network publishing, AI providers, and analytics are not connected; the UI/API must not represent those as live.

## Run locally with Docker

Requirements: Docker Engine and Docker Compose v2.

1. Copy `.env.example` to `.env`.
2. In `.env`, set a private PostgreSQL password consistently in `POSTGRES_PASSWORD`, `DATABASE_URL`, and `DATABASE_URL_SYNC`. Set `INITIAL_ADMIN_EMAIL` to a valid email address and a long `INITIAL_ADMIN_PASSWORD` for the local administrator. These values stay in the ignored `.env`; never commit them. The email must pass standard email validation (reserved `.test` domains are rejected).
3. Run `docker compose up --build -d` from the repository root. Compose waits for PostgreSQL and Redis, applies Alembic migrations, then starts the API and web app.
4. Open <http://localhost:3000> and sign in with the administrator configured above.

Useful checks:

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

The API is available at `http://localhost:8000`; interactive API documentation is at `/docs` in development. The dashboard, operational settings, persona drafts, adult-age validation, approval versions, bulk onboarding, mock caption drafts, and mock image/media preview are available after login. Live AI providers, accounts, calendar, publishing, campaigns, and analytics remain unconfigured. PostgreSQL and Redis have no published host ports. The API port is published for local development; production deployment must put the web app/API behind HTTPS and publish neither database nor Redis.

Stop services with `docker compose down`. Persistent database/Redis data stays in named volumes. `docker compose down -v` permanently removes that local data.

## Host development

Use Python 3.14 and Node.js 22 with npm 10. Install backend development dependencies with `python -m pip install -e ".[dev]"` from `backend`, and frontend dependencies with `npm ci` from `frontend`. Run backend lint/type-check/tests from `backend` (`ruff check app tests`, `mypy app`, `pytest`) and frontend checks from `frontend` (`npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build`). Docker image builds run these checks before producing the runtime images.

## Security and data boundaries

- Session tokens are random, stored hashed in PostgreSQL, and sent only in HTTP-only cookies. Production requires `APP_ENV=production` and `SESSION_COOKIE_SECURE=true` behind HTTPS.
- Admin bootstrap is optional and reads only private environment variables. There is no public registration/reset flow yet.
- Do not add social passwords, API keys, tokens, or other credentials to source, logs, images, or API responses.
- Only official social APIs may be used. No scraping or browser login automation is part of this project.
- Provider and platform integration status remains `not_configured` / `NEEDS_CREDENTIALS` until its official contract, credentials, and tests exist.
- Image generation currently uses a deterministic `MOCK` provider only. Image bytes use local development storage; production requires an authenticated S3-compatible adapter. No API key is exposed to the frontend.
- All counts on the initial dashboard are actual empty database-backed values; external metrics and generation cost are shown unavailable.

## Deployment status

Docker Compose is a local foundation, not yet a VPS-ready public deployment. Caddy/Nginx TLS, production Compose overrides, backup/restore automation, monitoring, rate limiting, and a deployment rollback procedure are part of production hardening. See [PROJECT_PLAN.md](PROJECT_PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), [API_SPEC.md](API_SPEC.md), [TEST_PLAN.md](TEST_PLAN.md), and [PROGRESS.md](PROGRESS.md).
