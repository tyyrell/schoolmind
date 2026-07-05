# Deployment Checklist

## Database

- Create a Supabase project.
- Use Supabase Session Pooler for one Render instance.
- Use Transaction Pooler for autoscaling or multiple instances.
- Set `DATABASE_ENGINE=postgres`.
- Set `DATABASE_URL=<Supabase pooler connection string>`.
- Remove `DATABASE_PATH` from production.
- Keep `DATABASE_PATH` only for local/dev/test SQLite.

## Render

```bash
APP_ENV=production \
SESSION_COOKIE_SECURE=true \
DATABASE_ENGINE=postgres \
DATABASE_URL="postgresql://user:password@host:6543/postgres?sslmode=require" \
AUTO_INIT_DB=true \
RUN_MIGRATIONS_ON_BOOT=true \
SECRET_KEY="replace-with-32-plus-chars" \
PUBLIC_BASE_URL="https://schoolmind.example.com" \
PLATFORM_ADMIN_PASSWORD="replace-with-strong-password" \
SEED_DEMO_DATA=false
```

## Verify

- `/api/health` responds.
- `/api/readiness` returns `database: true` and `database_engine: postgres`.
- Platform admin can log in.
- School admin can export workspace JSON.
- Billing webhook test passes with a valid signature.
- Invite, reset-password, Nour, role-boundary, CSRF, and backup tests pass.
