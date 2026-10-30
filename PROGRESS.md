# Progress

## 2026-10-30 — Content factory MVP

- Added owner-scoped generation jobs, content items, immutable caption versions, and append-only approval events in Alembic migration `20261030_0005`.
- Added a typed `CaptionProvider` interface and deterministic `MockCaptionProvider`; generated drafts are visibly identified as `mock/template-v1`. This is not an external AI integration. Image generation remains unconfigured.
- Added API/UI for draft creation from an approved owned persona, content listing, and explicit approve/reject decisions. Approval records the exact content version reviewed; non-drafts cannot be reviewed again.
- Added API tests for draft persona rejection, mock provider disclosure, approval gate, and owner isolation.
- Backend checks pass: Ruff, mypy (`45` source files), `29` pytest tests, and production image build. Frontend ESLint, TypeScript, `4` Vitest tests, and production image build pass.
- `docker compose up -d` applied migration `0005`; PostgreSQL, Redis, backend, and frontend remained healthy.
- Live PostgreSQL/API smoke passed: create a mock caption draft for an approved persona, verify persisted listing and generation-job ID, approve the exact draft, reject repeated approval with HTTP `409`, and load `/content` with HTTP `200`.

Remaining content factory work includes caption editing/version increments, real provider integrations, async worker execution, image generation/media storage, cost controls, and retries.

## 2026-10-30 — Operational controls and persona onboarding

### Implemented in the repository

- Added a responsive workspace navigation and honest status pages for every requested top-level area.
- Added an operational settings page backed by the existing authenticated API. Server-side validation bounds numeric controls and validates IANA timezones; setting changes remain audited.
- Added owner-scoped adult persona drafts, immutable approval snapshots, draft edit/resume, version history, and 18+ checks at API/database layers.
- Added persisted, resumable persona batches with per-candidate target labels, select-many approval, and candidate isolation. Candidate regeneration returns `NEEDS_CREDENTIALS` without mutating data because no AI provider is configured.
- Added forward migrations `20261029_0003` (personas/versions) and `20261030_0004` (batches/candidates), API contracts, and tests.

### Validation actually performed for this work

- Backend Ruff passed; strict mypy passed (`39` source files); pytest passed (`27 passed`, `6 warnings`); production backend image build passed.
- Frontend ESLint, TypeScript, Vitest (`3` files, `4` tests), and Next.js production build passed.
- `docker compose up -d` applied migration `0004`; PostgreSQL, Redis, backend, and frontend all reported `healthy`.
- Live PostgreSQL/API smoke test passed: authenticated login; create and resume two-candidate batch; approve only the selected candidate; verify the other remains `draft`; regeneration returns `503 NEEDS_CREDENTIALS` without changing the candidate; onboarding page returns HTTP `200`.
- Earlier local smoke tests passed for logout, dashboard, settings persistence/audit, and persona draft/approval/version immutability against PostgreSQL.

### Remaining product work

- Implement social account OAuth and social targets; persona-to-target assignments are not present yet. Bulk target labels are entered by the user and are not connected social accounts.
- Implement role management, actual Redis-backed rate limiting, worker/scheduler, and enforcement of kill-switch, cost, retry, and concurrency settings.
- Implement content/media providers, generation jobs, media handling, content approval, calendar, publishing/reconciliation, campaigns, and sourced analytics. External social/AI integrations still need official docs review and valid developer credentials.
- Audit the five npm advisories; VPS deployment, HTTPS, backup/restore, monitoring, and rollback remain outstanding.

## 2026-10-29 — Repository audit and foundation hardening

### Audit findings

- The repository is not empty. It contains planning docs and partial M0/M1 implementation. `.git` is absent, so Git status/history are unavailable. `rg.exe` is blocked in this environment.
- Backend: FastAPI, async SQLAlchemy, Alembic, PostgreSQL, hashed server-side sessions, initial-admin bootstrap, settings, audit logs, and notifications. Migrations cover those tables.
- Frontend: Next.js App Router, TypeScript, Tailwind, login, and an authenticated empty dashboard.
- Compose defines health-checked PostgreSQL and Redis with no published database/Redis ports. Backend startup applies migrations. The app health check now uses database readiness.
- Role authorization, rate limiting, structured operational logging, worker/scheduler and full kill-switch/budget/concurrency enforcement remain incomplete.
- Social/AI providers, personas, generation, publishing, campaigns, and external analytics are not implemented and remain `NOT_CONFIGURED` / `NEEDS_CREDENTIALS`.
- All required root planning documents and `.env.example` are present.

### Changes in this continuation

- Excluded host dependencies/caches from Docker build contexts; frontend context dropped from over 200 MB to about 330 KB.
- Fixed frontend image handling for the previously absent `public` directory and added `robots.txt`.
- Frontend image builds run ESLint, TypeScript, Vitest, and Next production build.
- Backend Dockerfile now has a dev-check stage followed by a lean runtime stage; checks include Ruff, mypy, and pytest.
- Local Compose uses PostgreSQL 16 (`postgres:16-alpine`) to match the compatible database image already present in the host Docker cache; PostgreSQL data uses the v16 `/var/lib/postgresql/data` volume path.
- Fixed existing Ruff issues, replaced a type-ignore in notification updates with typed `UPDATE … RETURNING`, and corrected notification test UUID fixtures.
- Added `backend/tests/__init__.py` so test imports resolve consistently in the container.
- Rewrote README local setup to match automatic migrations and private admin bootstrap; changed the Compose backend health check to database readiness.

### Validation actually performed

- Backend Docker check stage passed Ruff, mypy (`33` source files), and pytest (`20 passed`, `4 warnings`). The production backend image built.
- Frontend Docker build passed ESLint, TypeScript, Vitest (`2` files, `3` tests), and Next.js production build.
- `docker compose up -d` started PostgreSQL 16, Redis, backend, and frontend. All four containers reported `healthy`; PostgreSQL and Redis are not published on host ports.
- PostgreSQL startup ran both Alembic migrations and initialized the administrator.
- Live HTTP smoke test passed: `/login` returned `200`; `/health/live` and `/health/ready` returned `ok`; login returned `204`; authenticated `/auth/me` returned the configured admin identity; dashboard returned database `ok` and provider `not_configured`; logout returned `204`.
- The first local admin email (`admin@localhost.test`) was rejected by Pydantic email validation. The private `.env` now uses a syntactically valid local admin identity and login was verified after restarting the backend. No password or token was printed.
- npm reported `5` dependency advisories during `npm ci` (1 moderate, 2 high, 2 critical); advisory details and runtime impact have not yet been audited.
- Host Python/npm are not usable for checks in this environment; verification ran in Docker. `rg.exe` is unavailable and `.git` is absent, so Git status/history could not be obtained.

### Remaining work

- Services are running locally at `http://localhost:3000` (web) and `http://localhost:8000` (API). Local administrator email is `admin@ai-social-platform.com`; the randomly generated password is in the ignored private `.env`.
- Audit the npm dependency advisories and update dependencies only with compatible, verified fixes.
- Complete remaining M1 authorization/rate-limiting/operational-control requirements before personas or external integrations.
- VPS production hardening, personas, generation, scheduling/publishing, and campaign/analytics milestones remain unimplemented.
