# Phase 06 — Pricing and Billing UX

## Goal
Turn SchoolMind AI pricing from a simple price card into a credible SaaS billing path: 30-day evaluation trial, monthly and annual options, per-school pricing, included student limits, extra-seat policy, and provider-checkout guardrails.

## Implemented

- Rebuilt `/pricing` with:
  - 30-day evaluation trial wording.
  - Monthly and annual paths.
  - Annual effective monthly cost and annual savings.
  - Standard at $50/month with 300 included students.
  - Pro at $120/month with 1,000 included students.
  - Custom/guided pilot lane for large deployments.
  - Extra-student policy copy.
  - Plan comparison table.
  - Trial boundary and fake-free-funnel guardrails.

- Improved `/start` trial signup:
  - Captures intended post-trial billing cycle.
  - Preserves selected plan and billing cycle from query parameters.
  - Records intended billing cycle in trial-started billing event notes.
  - Clarifies that the trial is for evaluation, not uncontrolled production data collection.

- Improved admin billing dashboard:
  - Shows monthly and annual checkout actions.
  - Shows checkout configuration status per plan and billing cycle.
  - Keeps manual activation locked unless explicitly enabled.
  - Logs monthly vs annual checkout requests with the correct amount.

- Improved billing service:
  - Added normalized billing cycles.
  - Added annual savings and annual effective monthly calculations.
  - Added pricing catalog helper.
  - Added checkout URL support for `CHECKOUT_<PLAN>_MONTHLY_URL` and `CHECKOUT_<PLAN>_ANNUAL_URL`, with fallback to existing `CHECKOUT_<PLAN>_URL` variables.

- Added regression coverage:
  - `scripts/billing_audit.py`
  - Phase 06 tests in `run_tests.py`

## Validation

- `python3 scripts/billing_audit.py` — passed.
- `python3 scripts/route_audit.py` — passed, 106 endpoints checked.
- `python3 scripts/preflight.py` — passed with expected missing-production-config warnings.
- `python3 scripts/image_audit.py` — passed.
- `python3 scripts/i18n_audit.py` — passed.
- `python3 scripts/company_site_audit.py` — passed.

## Remaining owner inputs

Before real paid launch, provide payment-provider URLs and webhook secrets. Minimum recommended variables:

- `CHECKOUT_STARTER_MONTHLY_URL`
- `CHECKOUT_STARTER_ANNUAL_URL`
- `CHECKOUT_GROWTH_MONTHLY_URL`
- `CHECKOUT_GROWTH_ANNUAL_URL`
- `CHECKOUT_SCALE_URL` or a sales/demo request path
- `BILLING_WEBHOOK_SECRET`
