# Phase 12 — Security hardening

## Scope

Phase 12 tightened the application security layer without changing the product positioning or role workflows.

## Implemented changes

- Added safe same-origin redirect helpers:
  - `same_origin_url`
  - `safe_redirect`
  - `safe_referrer_redirect`
- Replaced unsafe `request.referrer` redirects in public preferences and guided demo lock flows.
- Centralized CSP construction in `build_content_security_policy()`.
- Preserved strict CSP with no `unsafe-inline` and no `unsafe-eval`.
- Added optional CSP reporting configuration:
  - `CSP_REPORT_ONLY`
  - `CSP_REPORT_URI`
- Added stricter browser isolation and hardening headers:
  - `Cross-Origin-Resource-Policy: same-origin`
  - `X-Permitted-Cross-Domain-Policies: none`
  - `X-DNS-Prefetch-Control: off`
  - `Origin-Agent-Cluster: ?1`
- Strengthened sensitive-page cache policy:
  - `Cache-Control: no-store, max-age=0`
  - `Pragma: no-cache`
  - `Expires: 0`
- Added production cookie hardening default:
  - `SESSION_COOKIE_NAME=__Host-schoolmind_session` in production
- Added runtime config for future rate-limit backend migration:
  - `RATE_LIMIT_BACKEND=memory|redis`
- Updated `.env.example` and `render.yaml` with the new security settings.
- Updated preflight checks for production cookie/CSP/rate-limit settings.
- Added `scripts/security_hardening_audit.py`.
- Added Phase 12 regression tests.

## Important limitation

`RATE_LIMIT_BACKEND=memory` remains acceptable for local development and controlled demos. Serious production traffic should use Redis or another shared backend so throttling survives restarts and works across multiple workers.

## Verification

- `python3 scripts/security_hardening_audit.py`
- `python3 scripts/ai_safety_audit.py`
- `python3 scripts/legal_trust_audit.py`
- `python3 scripts/dashboard_role_audit.py`
- `python3 scripts/onboarding_audit.py`
- `python3 scripts/trial_pilot_audit.py`
- `python3 scripts/billing_audit.py`
- `python3 scripts/company_site_audit.py`
- `python3 scripts/i18n_audit.py`
- `python3 scripts/image_audit.py`
- `python3 scripts/route_audit.py`
- `python3 scripts/preflight.py`
- Phase 12 regression tests in `run_tests.py`

## Production blockers still outside code

- Strong `SECRET_KEY`
- PostgreSQL/Supabase `DATABASE_URL`
- Real checkout URLs and webhook secret
- Real email provider
- Redis/shared rate limiting before serious production traffic
