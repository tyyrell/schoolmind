# Deployment

## Supported Target

The production target is a Render Web Service using Gunicorn and Supabase as managed PostgreSQL. SQLite is still supported for local development and automated tests only.

## Build And Start

```bash
pip install -r requirements.txt
gunicorn wsgi:app --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-8} --timeout 90
```

## Supabase Database

Create a Supabase project and copy a PostgreSQL connection string from the Connect panel.

Use:

- Session Pooler for one Render instance.
- Transaction Pooler for autoscaling or multiple Render instances.
- `sslmode=require` when provided by Supabase.

Do not use Supabase Auth for this app. SchoolMind keeps its existing Flask authentication, roles, sessions, CSRF, billing webhooks, and platform-admin controls.

## Required Render Environment

```txt
APP_ENV=production
SESSION_COOKIE_SECURE=true
DATABASE_ENGINE=postgres
DATABASE_URL=<Supabase pooler connection string>
AUTO_INIT_DB=true
RUN_MIGRATIONS_ON_BOOT=true
PUBLIC_BASE_URL=https://your-domain.example
SECRET_KEY=<32+ character secret>
PLATFORM_ADMIN_EMAIL=<operator email>
PLATFORM_ADMIN_PASSWORD=<strong operator password>
SEED_DEMO_DATA=false
ENABLE_DEMO_SEED=false
ALLOW_DEMO_DATA_IN_PRODUCTION=false
ALLOW_SELF_REGISTER=false
SCHOOLMIND_REQUIRE_INVITES=true
CHECKOUT_STARTER_URL=<provider checkout URL>
CHECKOUT_GROWTH_URL=<provider checkout URL>
CHECKOUT_SCALE_URL=<provider checkout URL>
BILLING_WEBHOOK_SECRET=<24+ character webhook secret>
```

Remove `DATABASE_PATH` from production. Keep it only in local `.env` files.

## Production Preflight

```bash
APP_ENV=production \
SESSION_COOKIE_SECURE=true \
SECRET_KEY="replace-with-32-plus-chars" \
PUBLIC_BASE_URL="https://your-domain.example" \
DATABASE_ENGINE=postgres \
DATABASE_URL="postgresql://user:password@host:6543/postgres?sslmode=require" \
PLATFORM_ADMIN_PASSWORD="replace-with-strong-password" \
SEED_DEMO_DATA=false \
python scripts/preflight.py
```

The preflight validates PostgreSQL configuration but does not print the database URL.

## Verify Deployment

1. Open `/api/health` for lightweight service health.
2. Open `/api/readiness` to verify database connectivity and schema version.
3. Sign in as the platform admin.
4. Open `/admin/database` inside a school workspace.
5. Create a non-demo school and verify users, billing state, backup export, and role boundaries.

## Rollback

1. Pause provider webhooks if billing behavior is affected.
2. Redeploy the previous known-good artifact or commit.
3. Keep the Supabase project intact; do not drop tables during rollback.
4. Verify `/api/readiness` after rollback.
5. If old SQLite data is needed, follow `docs/sqlite-to-supabase-migration.md` instead of copying production data by hand.
