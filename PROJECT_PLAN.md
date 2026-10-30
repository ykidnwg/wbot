# Project plan

## Product boundary

This repository implements an owner-scoped SaaS for fictional **adult** personas, media generation, review, scheduled publishing, and truthful analytics. It will use official APIs only. It will never store social-media passwords, use scraping/browser-login automation, fabricate a publication result, or represent an unavailable external metric as data.

## Technology decisions

| Concern | Choice | Reason |
| --- | --- | --- |
| Web UI | Next.js App Router, TypeScript, React, Tailwind CSS | Supported, typed UI with a production Docker deployment path. |
| API | FastAPI, Pydantic, SQLAlchemy async | Typed API contracts and async PostgreSQL access. |
| Schema migration | Alembic | Versioned, repeatable database changes. |
| Database | PostgreSQL | Durable relational storage and strong constraints. |
| Background work | Redis plus Celery worker/scheduler (milestone 2) | Persistent task state is in PostgreSQL; Redis is a broker/cache, not the system of record. |
| Tests | pytest, Vitest, Playwright (later) | Unit, API/integration, and browser coverage. |
| Deployment | Docker Compose; Caddy reverse proxy in production milestone | Isolated services, health checks, HTTPS, no public database/Redis ports. |

Current package versions are deliberately exact in the manifests. They were selected after checking the official Next.js documentation, FastAPI documentation/PyPI, SQLAlchemy documentation/PyPI, Alembic/PyPI, and Celery documentation on 2026-10-22; `asyncpg` is pinned to 0.32.0 after package-index verification of Python 3.14 support. Upgrades require review and a lock-file update.

## Milestones

### M0 — foundation (implemented in this change)

- Monorepo layout, documentation, environment contract, Docker Compose.
- FastAPI health/readiness endpoints, async PostgreSQL connection, Alembic initial migration.
- Owner-scoped `users` and server-side `sessions`; optional environment-provisioned initial admin.
- Next.js login and authenticated empty dashboard connected through a same-origin proxy.
- Backend and frontend tests; lint/type/build commands; local runbook.

### M1 — tenancy, audit, operational controls (partial)

- Production-ready user lifecycle, authorization roles, password reset or external OIDC decision.
- Audit log, settings, cost/concurrency/retry/kill-switch configuration, rate limiting, structured logs.
- Service health aggregation, notifications framework, authenticated shell/navigation.

Implemented so far: initial owner-scoped admin/session foundation, settings API/UI with bounds and audit, audit log/notification base, navigation, and honest status pages. Remaining: roles, rate limiting, structured operational logging, and enforcement/worker execution for kill switch, budgets, retries, and concurrency.

### M2 — personas and asset safety (partial)

- Personas, immutable approved versions, assignments, reference-image metadata and safe upload pipeline.
- Bulk candidate batches with isolated regeneration and draft/resume state.
- Object-storage abstraction (S3-compatible) and media validation/virus-scanning decision.

Implemented so far: adult persona drafts, immutable approved snapshots, versions, and resumable bulk candidate batches with isolated selection/approval. Regeneration is explicitly unavailable until an AI provider is configured. Social targets/assignments, reference uploads, object storage, and upload safety remain outstanding.

### M3 — generation and approval factory

Implementation status: partial; deterministic mock caption drafts and approval events are implemented. Async jobs, caption editing/versions, image generation, media assets, provider usage, retry/cost controls, and background execution remain.

- Provider interfaces and explicit mock provider; no paid provider is called in tests.
- Durable generation jobs, provider usage, content items, versions, approval events.
- Cost, concurrency and retry controls; idempotent retry semantics.

### M4 — scheduling and publishing core

- Calendar/list, explicit IANA timezone validation, conflict detection, persistent publishing jobs.
- Idempotency keys, retry taxonomy, `uncertain` reconciliation flow and audit events.

### M5 — Facebook Pages adapter

- Read the then-current official Meta Graph API documentation before coding.
- Record Graph version, endpoints, permissions, review requirements, response schemas, rate limits and test credentials in `docs/integrations/facebook-pages.md`.
- Implement token encryption, OAuth connection flow, target discovery, publishing/reconciliation adapter and mocked contract tests. Mark `NEEDS_CREDENTIALS` until exercised using valid permitted credentials.

### M6 — campaigns and analytics

- Campaign links, user-entered affiliate links, optional Adsterra configuration without invented reporting.
- Internal metrics plus source-labelled external snapshots; unavailable/stale states.

### M7 — remaining platform adapters

- Instagram, Threads and X one adapter at a time, each gated by official documentation, credentials, contract tests, and platform capability matrix.

### M8 — production hardening

- Caddy HTTPS deployment, backups/restore drill, monitoring, alerting, disaster recovery, load/security review, Playwright end-to-end suite.

## Required inputs before live integrations

1. Product owner, user/tenant model, and chosen authentication strategy (local accounts, OIDC, or both).
2. VPS domain/DNS, email sender, backup location/retention, and S3-compatible object-storage provider.
3. Meta business/app ownership, desired Facebook Page scopes/capabilities, app-review status, OAuth redirect URI, and test Page. No token is requested or stored in this repository.
4. Chosen AI image/caption providers, acceptable content policy, cost budget, supported countries, data-retention requirements, and moderator escalation policy.
5. Publishing policy: default timezones, allowed posting windows, approval roles, retry policy, and how uncertain outcomes are manually resolved.
6. Compliance review for affiliate disclosures, Adsterra links, platform policies, privacy policy, and account/operator access.

## Key risks and mitigations

| Risk | Mitigation |
| --- | --- |
| API capability or permission changes | Isolated adapters; version/capability records; official-doc review immediately before integration. |
| Duplicate posts after timeout | Idempotency key, persistent attempts, `uncertain` state, reconcile before resubmitting. |
| Token compromise | Encrypt at rest in a KMS-backed scheme in M5; HTTP-only sessions, secret manager, masking, revocation. |
| Unbounded AI cost | Per-user/provider daily/monthly budgets, worker concurrency, regeneration caps, kill switches. |
| Job loss on restart | Job state and retry schedule in PostgreSQL; workers claim atomically; broker is not the only record. |
| Persona identity drift | Versioned persona configuration; approved versions immutable; reference assets are advisory only. |
| Unsupported/fabricated analytics | Store source, period, retrieved-at and availability; show unavailable/stale when API lacks data. |
| Malicious uploads/URLs | Size/type verification, malware scan and SSRF allow-list before fetching remote resources. |

## M0 acceptance criteria

- [x] Repository contains all planning documents named in the request.
- [x] Environment template contains no usable credential or token.
- [x] Compose defines frontend, backend, PostgreSQL and Redis with internal-only database/Redis networking and health checks.
- [x] Alembic migration creates initial users/sessions schema and can be applied repeatedly through `upgrade head`.
- [x] Backend exposes liveness and database readiness checks without secrets.
- [x] Login uses a server-side, hashed session token in an HTTP-only cookie; it never returns a token body.
- [x] Empty dashboard requests the protected backend summary and labels all zero/unconfigured states honestly.
- [x] Automated backend, frontend, lint, type, migration and build checks are defined and run before handoff.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md), [API_SPEC.md](API_SPEC.md), [TEST_PLAN.md](TEST_PLAN.md), and [PROGRESS.md](PROGRESS.md).
