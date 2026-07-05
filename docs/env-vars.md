# Environment Variables

## Database

- `DATABASE_ENGINE`: `sqlite` for local development/tests, `postgres` for production/Supabase.
- `DATABASE_URL`: required when `DATABASE_ENGINE=postgres`. Use a Supabase PostgreSQL connection string. `postgres://` is accepted and normalized to `postgresql://` by the runtime.
- `DATABASE_PATH`: SQLite file path for local/dev/test only. Do not set this for normal production Supabase deployments.
- `ALLOW_SQLITE_IN_PRODUCTION`: emergency/demo escape hatch only. Leave `false` for real production.
- `AUTO_INIT_DB`: defaults to `true`; initializes idempotent schema on boot.
- `RUN_MIGRATIONS_ON_BOOT`: documented deployment flag for migration discipline; current startup migrations are controlled by `AUTO_INIT_DB`.

Render production should normally use:

```txt
DATABASE_ENGINE=postgres
DATABASE_URL=<Supabase Session Pooler connection string>
AUTO_INIT_DB=true
RUN_MIGRATIONS_ON_BOOT=true
```

Use Supabase Session Pooler for a single Render instance. Use Transaction Pooler when scaling horizontally or using autoscaling. Do not commit real connection strings.

## Core

- `APP_ENV`: `development`, `staging`, `production`, or `demo`.
- `SECRET_KEY`: required in production, 32+ characters.
- `PUBLIC_BASE_URL`: required HTTPS URL in production.
- `SESSION_COOKIE_SECURE`: must be `true` in production.
- `SEED_DEMO_DATA` / `ENABLE_DEMO_SEED`: must be `false` for real production.
- `ALLOW_DEMO_DATA_IN_PRODUCTION`: must stay `false` except for a controlled demo.

## Signup And Access

- `ALLOW_SELF_REGISTER`: `false` disables public `/start`.
- `SCHOOLMIND_REQUIRE_INVITES`: `true` makes invite-only deployments easier.
- `DEMO_MODE`: informational flag for hosted demos.

## Billing

- `CHECKOUT_STARTER_URL`
- `CHECKOUT_GROWTH_URL`
- `CHECKOUT_SCALE_URL`
- `BILLING_WEBHOOK_SECRET`: required for provider webhooks, 24+ characters when configured.

## Email

- `EMAIL_DELIVERY_MODE`: `queue`, `console`, or `smtp`.
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`
- `SUPPORT_EMAIL`

## Google OAuth

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `GOOGLE_DEFAULT_ROLE`
- `GOOGLE_DEFAULT_SCHOOL_SLUG`
- `GOOGLE_ALLOW_AUTO_CREATE`

## Platform Admin

- `PLATFORM_ADMIN_EMAIL`
- `PLATFORM_ADMIN_PASSWORD`
- `PLATFORM_ADMIN_NAME`

## Logging And Runtime

- `LOG_LEVEL`: defaults to `INFO`.
- `ENABLE_REQUEST_LOGGING`: defaults to `true`.
- `REQUEST_ID_HEADER`: defaults to `X-Request-ID`.
- `WEB_CONCURRENCY`
- `GUNICORN_THREADS`

## AI Provider Variables

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GROQ_TIMEOUT`

These may exist in hosting, but this release does not send student text to external AI providers by default.
