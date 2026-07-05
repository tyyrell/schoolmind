# SchoolMind AI

A clean rebuild of SchoolMind as a deployable Flask SaaS with a company-grade interface, mobile drawer navigation, tenant onboarding, role-based dashboards, personalization onboarding, student wellbeing scans, journals, goals, interactive skill games, breathing sessions, local Nour AI chat, progress reporting, weekly summaries, support-plan tracking, persistent language/theme/accessibility preferences, help and activity centers, counselor case briefs, teacher aggregate pulse, admin controls, Google sign-in support, account security center, platform owner console, coupon management, editable public-site settings, operations center, consent tracking, agreement acceptance records, invite onboarding, outbox email queue, SMTP/console dispatch, password reset flow, bulk imports, playbooks, lead capture, CSV/JSON backup export, Admin Backup Center, provider webhook billing, payment-intent records, subscription access control, and data retention cleanup.

## What this product is

SchoolMind is an educational support workflow system. It organizes support indicators and routes them to authorized school staff. It is not a diagnostic product and must not be sold as a medical or emergency service.

## Product depth added in this build

- Student Wellbeing Studio with an eight-domain scan: mood, stress, sleep, belonging, study pressure, focus, safety, and support access.
- Automatic non-diagnostic support plans after scans.
- Student journals, personal goals, skill games, breathing practice, mood diary, resources, daily tips, and local Nour AI history.
- Persistent account preferences for English, Arabic RTL, Spanish, French, Chinese, six themes, font size, reduced motion, high contrast, and dyslexia-friendly display.
- First-visit personalization onboarding for guests and authenticated users with database/session persistence.
- Nour AI now supports an AJAX chat endpoint with CSRF, plan limits, consent checks, saved messages, and human-review signal routing.
- Student progress hub, weekly wellbeing summary, support plan history, resource filters, interactive games, help center, activity center, and admin plan limits.
- Counselor focus queue and student support briefs.
- Counselor-authored support plans from the student case view.
- Teacher classroom pulse based on aggregated scan domains and practice engagement, not private journals.
- Reports expanded with wellbeing scan volume, average score, review load, focus areas, goals, games, breathing sessions, and Nour usage.
- Workspace JSON and student CSV exports now include wellbeing assessments, support plans, goals, games, breathing, AI metadata, subscriptions, payment intents, and coupon redemptions.
- Platform owner can create/disable coupon codes and update public homepage settings from `/platform`.
- Google OAuth routes are included and activate when `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` are configured.
- Hosting aliases supported: `ENABLE_DEMO_SEED`, `DEMO_MODE`, `ALLOW_SELF_REGISTER`, `SCHOOLMIND_REQUIRE_INVITES`, `WEB_CONCURRENCY`, and `GUNICORN_THREADS`.

## Stack

- Python 3.12+
- Flask 3
- PostgreSQL/Supabase for production; SQLite retained for local development and tests
- Gunicorn for production serving
- Vanilla HTML/CSS/JS

## Demo accounts

All demo accounts use this password:

```txt
demo12345
```

- admin@schoolmind.ai
- counselor@schoolmind.ai
- teacher@schoolmind.ai
- student@schoolmind.ai
- owner@schoolmind.ai for `/platform/login`

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="dev-secret-change-me"
export AUTO_INIT_DB=true
export SEED_DEMO_DATA=true
python app.py
```

Open:

```txt
http://localhost:5000
```

## Tests

```bash
python3 run_tests.py
python3 scripts/audit.py
python3 scripts/route_audit.py
SECRET_KEY="this-is-a-very-long-production-secret-key-123" PUBLIC_BASE_URL="https://schoolmind.example.com" DATABASE_ENGINE=postgres DATABASE_URL="postgresql://user:password@host:6543/postgres?sslmode=require" CHECKOUT_STARTER_URL="https://checkout.example.com/starter" CHECKOUT_GROWTH_URL="https://checkout.example.com/growth" CHECKOUT_SCALE_URL="https://checkout.example.com/scale" APP_ENV=production PLATFORM_ADMIN_PASSWORD="StrongPlatformPass123" python3 scripts/preflight.py
```

## Render deployment

1. Push this folder to GitHub.
2. Create a new Render Web Service.
3. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn wsgi:app`
4. Create a Supabase project and copy a PostgreSQL pooler connection string.
5. Set environment variables:
   - `APP_ENV=production`
   - `SECRET_KEY`
   - `SESSION_COOKIE_SECURE=true`
   - `DATABASE_ENGINE=postgres`
   - `DATABASE_URL=<Supabase pooler connection string>`
   - `AUTO_INIT_DB=true`
   - `SEED_DEMO_DATA=false` for real production
   - `ALLOW_DEMO_DATA_IN_PRODUCTION=false` unless running a locked demo environment
   - `CHECKOUT_STARTER_URL`
   - `CHECKOUT_GROWTH_URL`
   - `CHECKOUT_SCALE_URL`
   - `BILLING_WEBHOOK_SECRET` for provider webhook activation
   - `EMAIL_DELIVERY_MODE=queue|console|smtp`
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` when using SMTP
   - `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_PASSWORD`, `PLATFORM_ADMIN_NAME` for SaaS operator access
   - `ALLOW_SELF_REGISTER=false` or `SCHOOLMIND_REQUIRE_INVITES=true` for invite-only sales deployments
   - `WEB_CONCURRENCY` and `GUNICORN_THREADS` for Gunicorn capacity tuning
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_DEFAULT_ROLE`, `GOOGLE_DEFAULT_SCHOOL_SLUG`, and `GOOGLE_ALLOW_AUTO_CREATE` for Google sign-in
   - `GROQ_API_KEY` and `GROQ_MODEL` may exist in hosting, but this release keeps student AI local by default to avoid sending sensitive student text to a third party without explicit legal approval.

## Platform admin

Use `/platform/login` for the SaaS operator console. It shows all schools, sales leads, billing events, school status, user counts, operational risk, recent coupons, and public-site settings. The demo platform owner is `owner@schoolmind.ai` / `demo12345`; change this through environment variables before any public deployment.

## Billing

Billing is provider-ready. Add checkout links from your payment provider to the environment variables. The webhook endpoint `/api/billing/webhook` accepts HMAC-signed provider events and activates the matching school plan. Manual activation supports coupon validation, payment-intent records, subscription status, plan access, and redemption tracking. This is safer than hardcoding a provider that may not support your business country.

## Production hardening required before real schools

Do not deploy to real student users without:

- Lawyer-reviewed privacy policy and terms
- Agreement/version tracking reviewed for your region
- Parent/guardian consent workflow where required
- School incident response protocol
- External security review
- Supabase database backups plus the app workspace JSON export
- Data retention and deletion policy
- Region-specific support escalation procedure

## Architecture

```txt
schoolmind/
  __init__.py          App factory
  auth.py              Login and tenant onboarding
  dashboard.py         Role dashboards, student tools, billing, account security, operations center, and case workflows
  platform.py          SaaS operator console, coupon management, and public site settings
  api.py               Health, readiness, pulse, exports, billing webhook
  db.py                SQLite schema and data access
  security.py          CSRF and security headers
  decorators.py        Login and role guards
  services/
    analyzer.py        Safe educational signal analyzer
    billing.py         Plan, coupon, subscription, and checkout helpers
    google_oauth.py    Google sign-in helpers
    mailer.py          Outbox email queue and SMTP dispatch
    tokens.py          Secure invite token hashing
    validators.py      Input validation and normalization
  templates/           Jinja UI
  static/              SchoolMind AI design system and JS
```

## Latest build notes

- Added event-level case actions: assign, escalate, close, and note.
- Added urgent escalation email queuing through the outbox.
- Added admin Operations Center for launch checks, seat usage, SLA overdue count, email queue status, backup, and retention cleanup.
- Added agreement acceptance records for workspace creation and invite acceptance.
- Added account lockout, login security events, Admin Security Center, unlock controls, and admin-queued reset links.
- Added Platform Admin console for SaaS-level school, lead, billing, and status oversight.
- Added tenant suspension enforcement so suspended/cancelled schools cannot continue using protected workspace routes.
- Added production runtime guard against accidental demo seeding.
- Added Admin Backup Center and manual restore runbook.
- Added route audit script for endpoint map checks.
- Added student journals, goals, skill games, breathing center, mood diary, daily tips, and resources as first-class pages.
- Added local Nour AI conversation storage with daily plan limits.
- Added Google sign-in routes and safe disabled-state handling.
- Added real coupon validation, redemptions, payment-intent records, and subscription status enforcement.
- Added Platform coupon management and server-stored public homepage settings.
- Expanded automated coverage to 57 tests, including PostgreSQL config/schema safety checks.
- Added mobile product polish: role-aware mobile drawer, active navigation, first-screen focus reset, action integrity checks, personalization onboarding, interactive games, Help Center, Activity Center, and Admin Plan Limits.

## Database and release readiness

- Production runtime now uses `DATABASE_ENGINE=postgres` with a Supabase PostgreSQL `DATABASE_URL`.
- SQLite remains available through `DATABASE_ENGINE=sqlite` and `DATABASE_PATH` for local development and tests.
- Production rejects SQLite unless `ALLOW_SQLITE_IN_PRODUCTION=true` is explicitly set for a controlled demo exception.
- Admins can review database status at `/admin/database`.
- Run `python3 scripts/release_check.py` before packaging a final customer ZIP.

## Latest build notes continued

- Added Admin Database Readiness screen with schema version, table counts, runtime path, release artifact scan, and PostgreSQL blocker visibility.
- Added final mobile hardening: better small-screen cards, full-width actions, focus states, reduced-motion support, menu ARIA state, and Escape-to-close navigation.
- Added Supabase/PostgreSQL runtime support, `docs/database.md`, `docs/sqlite-to-supabase-migration.md`, and `docs/RELEASE_CHECKLIST.md`.
- Added `scripts/release_check.py` to block runtime databases, caches, and incomplete release artifacts before final packaging.


## Final release packaging

Use the release builder instead of zipping the folder manually:

```bash
python3 scripts/build_release.py
```

The builder runs compile, tests, audit, production-style preflight, route audit, release cleanup, and release scan before creating the ZIP. It excludes runtime databases, cache folders, bytecode, local `.env`, logs, and `instance/`.

Final release docs:

- `docs/RELEASE_NOTES.md`
- `docs/FINAL_QA_REPORT.md`
- `docs/FINAL_RELEASE_MANIFEST.json` after packaging
- `docs/production-readiness.md`
- `docs/security.md`
- `docs/deployment.md`
- `docs/env-vars.md`
- `docs/incident-response.md`
- `docs/testing.md`
- `docs/billing.md`
- `docs/i18n.md`
- `docs/ux-upgrade.md`
- `docs/themes.md`
- `docs/mobile-qa.md`
- `docs/action-integrity.md`
