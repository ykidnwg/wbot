# Test plan

## Test layers

| Layer | Tool | M0 coverage |
| --- | --- | --- |
| Backend unit/API | pytest + httpx | health, auth/session, settings bounds and auditing, persona age/ownership/version immutability, batch isolation, mock content disclosure, approval gate and owner isolation. |
| Database integration | pytest + aiosqlite test DB | ORM model metadata and schema behaviors used by M0 endpoints. PostgreSQL migration is exercised in Compose. |
| Frontend unit | Vitest + Testing Library | login form, honest dashboard states, adult persona draft submission. |
| Static checks | Ruff, mypy, ESLint, `tsc --noEmit` | formatting/lint/type correctness. |
| Build | Next build, Docker Compose build | production frontend/backend build paths. |
| Browser E2E | Playwright (M1) | login through proxy and authenticated navigation after a repeatable test-user fixture exists. |

## Foundation commands

```powershell
# Image build runs backend Ruff + mypy + pytest and frontend ESLint + tsc + Vitest + Next build.
docker compose --env-file .env.example build

# For a local run, copy .env.example to .env and set private DB/admin values first.
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

The runtime containers do not include test tools. Run backend checks with `docker compose build backend` and frontend checks with `docker compose build frontend`; each check stage is required for the production image build. Host development can instead use `pip install -e ".[dev]"` from `backend` and `npm ci` from `frontend`, followed by the matching scripts in the package manifests.

## Latest recorded execution

See `PROGRESS.md` for the actual commands/results. Backend production image build passed with Ruff, mypy, and 29 pytest tests. Frontend production image build passed with ESLint, TypeScript, 4 Vitest tests, and Next production build. Compose applied migrations through `0005`; all four services were healthy. Live smoke covered login, persisted batch creation/resume, selective approval isolation, unconfigured-provider response, and onboarding page HTTP 200. Content smoke covered persisted mock draft creation/listing, generation job linkage, successful explicit approval, repeated-approval rejection (`409`), and content page HTTP 200. Earlier smoke tests covered logout, dashboard, settings save/audit, and persona version approval.

## Later acceptance tests

- M1: authorization isolation, session rotation/revocation, rate limit and audit-log tests.
- M2: bulk candidate regeneration isolation, immutable approved persona version, upload/SSRF constraints.
- M3: job transition state machine, retry classification/backoff/jitter, concurrency and budget guardrails.
- M4: timezone/DST, duplicate schedule prevention, approval gate, idempotency and `uncertain` reconciliation.
- M5/M7: recorded official-API contract fixtures for success, expired token, permission, validation, rate limit, timeout and unavailable endpoint. Live smoke tests require separate explicitly authorized credentials.
- M8: backup/restore drill, health/restart recovery, TLS/security headers, load test and Playwright suite.
