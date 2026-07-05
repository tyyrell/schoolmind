# Phase 04 — Bilingual / RTL Foundation

## Status
Completed in the active Phase 17 working tree.

## What changed
- Added public company-site translation keys for English and Arabic.
- Converted the homepage from hardcoded English copy to translation-driven copy.
- Kept English as the default experience.
- Made Arabic render with real Arabic marketing copy, not only `dir="rtl"`.
- Added a persistent language switcher in the main navigation.
- Added language links that preserve the current public path, for example `/pricing?language=ar` and `/pricing?language=en`.
- Localized core base-shell text: skip link, brand subtitle, footer statement, navigation labels, and guided demo nudge text.
- Added RTL CSS refinements for company cards, pricing cards, timeline blocks, lists, footer, nav, demo banner, and language switcher.
- Added `scripts/i18n_audit.py` to prevent future regressions.
- Added regression tests for Arabic homepage copy and language switcher behavior.

## Product decision
English remains default. Arabic is supported as a first-class public-site experience. The current phase focuses on the public marketing shell and homepage; deeper dashboard-level Arabic copy already uses the existing translation helper where keys exist and will continue being expanded in later dashboard/onboarding phases.

## Validation
- `python3 scripts/i18n_audit.py` passed.
- `python3 run_tests.py` passed: 79 passed, 1 skipped.
- `python3 scripts/route_audit.py` passed: 99 endpoints checked.
- `python3 scripts/preflight.py` passed with expected missing-production-secret/provider warnings.
