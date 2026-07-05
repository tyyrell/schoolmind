# Phase 08 — School Launch Onboarding

## Objective
Turn the post-signup admin experience into a controlled school launch path instead of dropping a new school into a blank dashboard.

## Implemented
- Added `schoolmind/services/onboarding.py` with a structured launch checklist and readiness model.
- Expanded `school_settings` with launch profile fields:
  - `launch_language`
  - `launch_mode`
  - `launch_stage`
  - `approval_owner`
  - `data_owner`
  - `support_email`
  - `expected_students`
  - `expected_staff`
  - `pilot_goal`
  - `onboarding_completed_at`
- Upgraded `/admin/onboarding` from a static checklist to a POST-capable launch workspace.
- Added a launch profile form, owner map, readiness score, blocker list, next-action CTA, and launch-ready/reset controls.
- Added CSS for the onboarding workspace without inline styles, preserving CSP compatibility.
- Added `scripts/onboarding_audit.py`.

## Product decision
A school cannot be treated as production-ready just because an account exists. The workspace must show owners, policy, consent, staff, roster, billing, and a human escalation protocol.

## Remaining production dependencies
- Real legal approval remains outside the app.
- Email delivery, production database, payment provider, and domain still require owner-supplied credentials.
