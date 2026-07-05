# PostgreSQL Migration Status

The PostgreSQL migration plan has been implemented in this build. SchoolMind now supports:

- `DATABASE_ENGINE=sqlite` for local development and tests
- `DATABASE_ENGINE=postgres` for production/Supabase
- `DATABASE_URL` with `postgres://` or `postgresql://`
- request-scoped PostgreSQL connections through `psycopg[binary]`
- placeholder conversion from `?` to `%s`
- PostgreSQL schema generation without `PRAGMA` or `AUTOINCREMENT`
- schema version `2026-07-pixel-saas-7-postgres`

Operational migration steps are now in `docs/sqlite-to-supabase-migration.md`. Database architecture details are in `docs/database.md`.
