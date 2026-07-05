# SQLite To Supabase Migration Guide

## 1. Create Supabase Project

1. Create a new Supabase project.
2. Choose the region closest to your school/customer data requirements.
3. Save the database password securely.
4. Do not enable Supabase Auth for SchoolMind. The app uses its own Flask authentication and role checks.

## 2. Get Connection String

Open the Supabase project Connect panel and copy a PostgreSQL connection string.

Use:

- Session Pooler for a single Render instance.
- Transaction Pooler for autoscaling or multiple Render instances.
- Direct connection only for controlled admin/migration operations when appropriate.

Keep `sslmode=require` when it appears in the connection string.

## 3. Set Render Environment

```txt
DATABASE_ENGINE=postgres
DATABASE_URL=<Supabase pooler connection string>
AUTO_INIT_DB=true
RUN_MIGRATIONS_ON_BOOT=true
APP_ENV=production
SESSION_COOKIE_SECURE=true
SEED_DEMO_DATA=false
ENABLE_DEMO_SEED=false
```

Remove `DATABASE_PATH` from production.

## 4. First Deploy

1. Deploy the updated ZIP/commit to Render.
2. The app runs idempotent schema initialization on boot when `AUTO_INIT_DB=true`.
3. Open `/api/readiness`.
4. Confirm JSON shows `database: true`, `database_engine: postgres`, and schema version `2026-07-pixel-saas-7-postgres`.

## 5. Migrating Existing SQLite Data

Do not overwrite production Supabase data blindly.

Safe staged approach:

1. Download a tenant workspace JSON export from the old SQLite deployment.
2. Preserve the old SQLite file offline as immutable evidence/backup.
3. Deploy Supabase schema first with an empty database.
4. Recreate schools/users through admin flows or a reviewed import script.
5. Import sensitive historical tables only after mapping old IDs to new IDs.
6. Verify counts for users, preferences, Nour messages, games, billing, coupons, consent, and audit records.

A fully automated destructive importer is intentionally not included because bad ID mapping can corrupt school-scoped student records and audit history.

## 6. Verify

- `/api/health`: service responds.
- `/api/readiness`: database connectivity is true.
- `/admin/database`: schema version and table counts render.
- `/api/export/workspace.json`: admin export still works.
- Login, role boundaries, billing webhook, Nour chat, invites, reset links, and CSRF-protected forms work.

## 7. Rollback Plan

1. Pause billing webhooks if needed.
2. Redeploy the previous artifact.
3. Do not drop the Supabase database.
4. If rolling back to SQLite for a demo only, set `ALLOW_SQLITE_IN_PRODUCTION=true` and a persistent `DATABASE_PATH`; do not use this for real production.
5. Re-run `/api/readiness` and a platform-admin login test.

## Known Limitations

- Old SQLite data migration is documented as a staged manual process, not an automatic bulk importer.
- Supabase Auth is not used.
- PostgreSQL integration tests run only when `TEST_DATABASE_URL` is available.
