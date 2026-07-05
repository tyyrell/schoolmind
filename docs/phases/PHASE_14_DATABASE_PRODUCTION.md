# Phase 14 — Database Production Readiness

## Goal

Move SchoolMind AI closer to a real production database posture without pretending that a hosted database has already been configured by the owner. The code is now more explicit about Supabase/PostgreSQL requirements, TLS, timeouts, migration state, and operator inputs.

## What changed

- Advanced `SCHEMA_VERSION` to `2026-07-schoolmind-postgres-14`.
- Added PostgreSQL URL helpers:
  - `postgres_url_settings`
  - `build_postgres_database_url`
  - `database_url_uses_supabase_pooler`
- PostgreSQL connections now support runtime-configured:
  - `DATABASE_SSLMODE`
  - `DATABASE_CONNECT_TIMEOUT_SECONDS`
  - `DATABASE_STATEMENT_TIMEOUT_MS`
  - `DATABASE_APPLICATION_NAME`
- Production PostgreSQL now requires TLS posture of `require`, `verify-ca`, or `verify-full`.
- Added `DATABASE_POOLING_MODE` to document whether the deployment is using an external/direct/transaction/session pooling posture.
- Expanded `/admin/database` with:
  - masked `DATABASE_URL`
  - Supabase/PostgreSQL readiness panel
  - TLS status
  - pooling posture
  - connect/statement timeout visibility
  - production database input checklist
- Expanded `scripts/preflight.py` to catch weak PostgreSQL production configuration before deploy.
- Added `scripts/postgres_readiness_audit.py` as a phase regression audit.
- Updated `.env.example` and `render.yaml` with production database variables.

## Production inputs required from owner

These values must be configured in Render or the production host. Do not commit them to the repository.

```text
DATABASE_ENGINE=postgres
DATABASE_URL=postgresql://...
DATABASE_SSLMODE=require
DATABASE_POOLING_MODE=external
DATABASE_CONNECT_TIMEOUT_SECONDS=10
DATABASE_STATEMENT_TIMEOUT_MS=30000
DATABASE_APPLICATION_NAME=schoolmind-ai
AUTO_INIT_DB=true
SEED_DEMO_DATA=false
```

## Not done by code

This phase does not create a Supabase project and does not prove a live PostgreSQL connection unless `TEST_DATABASE_URL` is supplied by the owner. It also does not replace operational database work:

- Supabase project creation.
- Database password rotation.
- IP/network policy review.
- Backup schedule configuration.
- Restore drill.
- Connection pool load testing.
- Legal review of data residency.

## Production rule

SQLite remains acceptable only for local development, tests, or an explicitly isolated demo. Paid school production must use PostgreSQL.

## Verification

Run:

```bash
python3 scripts/postgres_readiness_audit.py
python3 scripts/preflight.py
python3 scripts/route_audit.py
python3 run_tests.py
```

If `TEST_DATABASE_URL` is available, also run the optional PostgreSQL integration test:

```bash
TEST_DATABASE_URL='postgresql://...' python3 -m unittest run_tests.SchoolMindAITest.test_optional_postgres_integration_readiness -v
```
