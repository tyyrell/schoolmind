# Release Checklist

Run before handing a production ZIP to anyone:

```bash
python -m compileall -q .
python run_tests.py
python scripts/audit.py
python scripts/route_audit.py
python scripts/action_integrity.py
python scripts/i18n_report.py
APP_ENV=production SESSION_COOKIE_SECURE=true SECRET_KEY="this-is-a-real-32-character-secret-change" PUBLIC_BASE_URL="https://schoolmind.example.com" DATABASE_ENGINE=postgres DATABASE_URL="postgresql://user:password@host:6543/postgres?sslmode=require" CHECKOUT_STARTER_URL="https://checkout.example.com/starter" CHECKOUT_GROWTH_URL="https://checkout.example.com/growth" CHECKOUT_SCALE_URL="https://checkout.example.com/scale" PLATFORM_ADMIN_EMAIL="owner@example.com" PLATFORM_ADMIN_PASSWORD="StrongPlatformPass123!" BILLING_WEBHOOK_SECRET="webhook-secret-change-me" SEED_DEMO_DATA=false python scripts/preflight.py
python scripts/clean_release.py
python scripts/release_check.py
python scripts/build_release.py
```

Production requirements:

- `DATABASE_ENGINE=postgres`
- `DATABASE_URL=<Supabase pooler connection string>`
- no real secrets committed
- no `.sqlite`, `.db`, `.env`, `.pyc`, `__pycache__`, or logs in the artifact
- `/api/readiness` confirms database connectivity after deployment
