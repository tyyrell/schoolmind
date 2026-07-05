# Phase 15 — Performance and Mobile Polish

## Goal

Make the company-ready build feel credible on phones and slower school networks, without weakening CSP or hiding unfinished production dependencies.

## Implemented

- Added `schoolmind/static/css/performance-mobile.css` as a dedicated performance/mobile layer loaded after `company.css`.
- Added mobile safe-area padding for modern iOS/Android devices.
- Added `100dvh` viewport handling for mobile overlays.
- Strengthened mobile navigation with scroll containment and body scroll lock.
- Added global overflow protection so long emails, URLs, database strings, and legal text do not break the layout.
- Added tap target minimums for buttons, links, forms, and interactive controls.
- Added mobile-first button wrapping so CTA rows do not overflow.
- Added `content-visibility: auto` and `contain-intrinsic-size` to defer below-the-fold rendering work.
- Added image containment and explicit aspect-ratio handling for smart pictures.
- Added reduced-motion and reduced-data safeguards.
- Added table horizontal scrolling wrappers support for dense admin/legal views.
- Added RTL direction safeguards for the mobile shell.
- Added `scripts/performance_mobile_audit.py` and regression tests.

## Boundaries

This phase does not replace real browser/device QA. The next serious production pass still needs manual checks on narrow Android, iPhone SE-sized screens, tablet, and Arabic RTL.

## Verification

Run:

```bash
python3 scripts/performance_mobile_audit.py
python3 run_tests.py
python3 scripts/route_audit.py
python3 scripts/preflight.py
```
