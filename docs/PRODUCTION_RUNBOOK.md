# Production Runbook

## Preflight

```bash
APP_ENV=production SECRET_KEY="replace-with-32-plus-chars" PUBLIC_BASE_URL="https://schoolmind.example.com" PLATFORM_ADMIN_PASSWORD="replace-with-strong-password" DATABASE_ENGINE=postgres DATABASE_URL="postgresql://user:password@host:6543/postgres?sslmode=require" CHECKOUT_STARTER_URL="https://checkout.example.com/starter" CHECKOUT_GROWTH_URL="https://checkout.example.com/growth" CHECKOUT_SCALE_URL="https://checkout.example.com/scale" SEED_DEMO_DATA=false python3 scripts/preflight.py
```

## Daily checks

- Review `/api/readiness`.
- Review `/admin/database` for table counts and schema version.
- Review Operations Center for overdue support signals, outbox failures, and retention cleanup.
- Confirm Supabase backups are enabled according to the selected Supabase plan.

## Incidents

- Do not expose `DATABASE_URL` in logs or tickets.
- Pause billing webhooks if subscription updates are misbehaving.
- Keep the Supabase database intact during rollback.
- Use workspace JSON export for tenant-level review, not as the only disaster-recovery backup.
