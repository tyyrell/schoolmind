# Production Readiness

## Current Status

SchoolMind is ready for controlled pilots, sales demonstrations, and staged school deployments after the operator completes the manual production steps. It is not a medical, emergency, therapy, or diagnosis product.

## Implemented

- Flask app factory with production safety validation.
- Explicit SQLite/PostgreSQL engine selection.
- Supabase-compatible PostgreSQL runtime through `DATABASE_ENGINE=postgres` and `DATABASE_URL`.
- Secure session cookies with `HttpOnly`, `SameSite=Lax`, and production `Secure`.
- CSRF protection on state-changing form routes.
- Role-based dashboards for student, teacher, counselor, admin, and platform owner.
- Tenant isolation through school-scoped queries and role decorators.
- Password hashing with Werkzeug.
- Account lockout, password reset tokens, invite tokens, and login security events.
- Billing webhook signature verification and subscription state updates.
- Coupon creation, disabling, validation, and redemption tracking.
- Payment-intent records for provider webhooks and manual activation.
- Student data export and workspace JSON backup.
- Nour chat API with CSRF, consent checks, plan limits, saved messages, and support-signal routing.
- Admin retention cleanup.
- Health and readiness endpoints with database connectivity checks.
- Structured JSON request logging with database URL masking.
- CI-style scripts for compile, tests, audit, preflight, route audit, cleanup, and release scan.

## Operator Must Complete

- Create and secure a Supabase project.
- Set `DATABASE_ENGINE=postgres` and a Supabase pooler `DATABASE_URL` on Render.
- Remove `DATABASE_PATH` from production.
- Configure payment provider checkout URLs and webhook secret.
- Configure SMTP before claiming email delivery.
- Review legal text with counsel before real student usage.
- Establish a school-approved human escalation protocol.
- Enable and test Supabase backup/restore expectations.
- Run `python run_tests.py`, `python scripts/preflight.py`, and `python scripts/route_audit.py` before launch.

## Not Implemented By Design

- Supabase Auth. The app intentionally keeps existing Flask auth.
- Automatic destructive restore. Restore is manual to avoid damaging audit/legal records.
- External AI processing of student text. Nour stays local by default unless a future privacy-approved integration is added.
- Legal compliance certification. The app supports compliance workflows but does not claim GDPR, CCPA, FERPA, or regional compliance by itself.
