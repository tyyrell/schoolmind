# Render PostgreSQL Startup Hotfix

## Problem fixed

Render failed during Gunicorn startup with:

```text
psycopg.errors.UndefinedColumn: column "lead_type" does not exist
```

The cause was migration order, not Render itself. The app created tables and indexes from the schema before running `migrate_database()`. Existing PostgreSQL deployments can already have an older `sales_leads` table without the Phase 7 lead fields. The schema then tried to create `idx_leads_type_status` on `sales_leads(lead_type, status, created_at)` before the `lead_type` column had been added.

## Fix applied

`schoolmind/db.py` now runs database initialization in the safe order:

1. Create missing tables only.
2. Run `migrate_database()` to add missing columns to existing tables.
3. Create indexes and other post-migration schema objects.
4. Record schema version and seed required defaults.

This preserves existing production data and does not require dropping or resetting the database.

## Regression tests added

Two tests were added to `run_tests.py`:

- `test_phase_17_hotfix_post_migration_indexes_do_not_run_before_column_backfills`
- `test_phase_17_hotfix_existing_sales_leads_table_gets_new_columns_before_index_creation`

These prevent future regressions where an index references a migrated column before the column is created.

## Deploy instruction

Deploy this hotfix ZIP over the current Render service. Do not reset the database. On startup, the app should add the missing `sales_leads` columns, then create the indexes successfully.
