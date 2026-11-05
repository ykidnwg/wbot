# Browser-First Automation Plan

## Goal

Make isolated browser automation the primary publishing path while preserving the existing approved-content, scheduling, analytics, and Graph API foundations. The browser worker is a separate process; the API remains the control plane and PostgreSQL remains the source of truth.

## Safety Boundaries

- No CAPTCHA, MFA, security-check, rate-limit, or platform-policy bypass.
- No stealth fingerprinting, proxy rotation for evasion, credential harvesting, or unauthorized scraping.
- Manual login only in a visible browser owned by the operator.
- Passwords are never stored. Session state is encrypted with `TOKEN_ENCRYPTION_KEY` and never returned by the API or written to logs.
- An ambiguous publishing outcome becomes `UNKNOWN` and is never retried automatically.
- Each account can run at most one job at a time.
- Live platform automation is disabled until a specific adapter is reviewed and a real account is used manually. Tests use local fixtures and fake runtimes.

## Architecture

- `browser_accounts`: owner-scoped platform identity and health metadata.
- `browser_profiles`: one encrypted Playwright storage-state record per account. No plaintext persistent Chromium profile is kept on disk.
- `browser_jobs`: durable queue with uppercase states, idempotency key, account-level locking, attempt count, safe outcome metadata, and timestamps.
- `browser_job_events`: append-only, owner-scoped job activity trail with safe messages.
- `browser_workers`: worker heartbeat and current-job visibility.
- Schedules gain an optional `browser_account_id`; exactly one of `social_target_id` or `browser_account_id` is set.
- Celery + Redis run the browser queue cycle. PostgreSQL row locks (`FOR UPDATE SKIP LOCKED`) provide the durable claim.
- Playwright runtime is behind an interface so unit tests never launch a browser.

## State Machine

Browser job states: `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, `NEEDS_USER_ACTION`, `UNKNOWN`, `CANCELLED`.

- `QUEUED` -> `RUNNING` on atomic claim.
- Publish adapter returns an explicit outcome.
- A confirmed post -> `SUCCESS`.
- A pre-submit validation/network/session failure may return to `QUEUED` with backoff.
- A missing/expired session -> `NEEDS_USER_ACTION`.
- An exception or timeout after submit, or a stale `RUNNING` job, -> `UNKNOWN`.
- `FAILED` and `NEEDS_USER_ACTION` are manual-review states. `UNKNOWN` is never automatically retried.
- Only `FAILED` may be manually retried, and only after operator verification that no post was created.

## Milestones

### M1: Audit and contract
- Inventory existing API, worker, schema, UI, and Docker conventions.
- Record this plan.
- Verification: plan reviewed against repository.

### M2: Worker and runtime foundation
- Add Celery/Redis/Playwright dependencies and a separate browser worker service.
- Add browser accounts, profiles, jobs, events, worker heartbeat models and additive migration.
- Add encrypted session-state helpers and safe event logging.
- Add fake runtime and unit tests.

### M3: Profiles and manual login
- Account/profile CRUD and owner isolation.
- Login job type launches a visible runtime when a display is configured; otherwise returns a clear `NEEDS_USER_ACTION`.
- Capture encrypted storage state only after operator confirmation.
- Session health check job.

### M4: Monitoring and recovery
- Dashboard counters and APIs for accounts, session health, worker heartbeat, jobs, manual-action queue, history, and events.
- Stale `RUNNING` jobs become `UNKNOWN`; they are never automatically repeated.
- Account-level concurrency lock and idempotent job creation.

### M5: Scheduler integration
- Add optional browser-account destination to schedules.
- Dispatch due browser schedules into `browser_jobs` with idempotency `browser-schedule:{schedule_id}`.
- Keep legacy Graph-API dispatch for existing `social_target_id` schedules.
- Update calendar UI to choose a browser account or a Page.

### M6: First platform workflow
- Define platform adapter boundary and local fixture adapter.
- Add a guarded Facebook workflow. Real publishing remains disabled until explicitly enabled and manually reviewed; safety stops convert to `NEEDS_USER_ACTION` or `UNKNOWN`.
- Verification: local fixture integration plus contract tests; no claim of live Facebook success without a real manual test.

### M7: Additional platforms
- Add adapters only after the first workflow is reviewed.
- No adapter may share plaintext sessions, profile directories, or account locks.

### M8: Hardening and documentation
- Add rate/ownership/timezone/idempotency regression tests.
- Update README, architecture, schema, API, test plan, deployment, and operational runbooks.
- Run backend lint/typecheck/tests, frontend lint/typecheck/tests/build, migration upgrade, and Compose smoke.

## Test Strategy

- Backend unit/integration: owner isolation, encrypted state, idempotency, account locking, state transitions, stale recovery, scheduler dispatch, adapter safety, migration contract.
- Browser runtime: fake runtime only in tests. Playwright smoke runs only when explicitly enabled.
- Frontend: API mapping and dashboard/account/job states with Vitest; production build must pass.
- Live: requires credentials/display and is reported separately from automated verification.
