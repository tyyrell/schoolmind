# Backup And Restore Runbook

## Current backup model

SchoolMind exports tenant-level JSON from `/api/export/workspace.json` and the Admin Backup Center. The export is scoped to the current school workspace and includes preferences, personalization flags, Nour messages, games, breathing, billing, coupons, subscriptions, consent, support workflows, and audit/activity records.

For production, Supabase managed PostgreSQL backups are the database-level backup source. The app export is useful for tenant review, operational exports, and staged migration support; it is not a replacement for database backups.

## Before production

1. Confirm Supabase backup/PITR expectations for the selected plan.
2. Run `/api/readiness`.
3. Download a workspace JSON export from a test school.
4. Verify table counts in `/admin/database`.
5. Store secrets outside the repository.

## Manual restore discipline

Automatic destructive restore is intentionally not implemented. Restore should be reviewed because school-scoped IDs, audit records, consent records, billing state, and support history can be damaged by blind imports.

Use `docs/sqlite-to-supabase-migration.md` for migration from an old SQLite deployment.
