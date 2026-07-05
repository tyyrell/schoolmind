# Phase 09 — Role-Specific Dashboards

## Goal
Turn the four core workspaces into role-specific command centers instead of generic metric pages.

## Implemented
- Added `schoolmind/services/role_dashboards.py` to centralize role command-center logic.
- Added `schoolmind/templates/partials/role_command_center.html` as a reusable dashboard block.
- Updated student, teacher, counselor, and admin dashboards to include role-specific priorities, KPIs, and workflow actions.
- Added teacher privacy boundary cards so the teacher view remains aggregate-only.
- Added admin governance snapshot cards for support owner, data owner, and launch mode.
- Added responsive CSS for role command centers, KPI cards, workflow cards, and RTL behavior.
- Added `scripts/dashboard_role_audit.py` to prevent future regressions.

## Product impact
- Student dashboard now prioritizes consent, scan, support plan, and progress flows.
- Teacher dashboard now emphasizes aggregate class patterns without exposing private student content.
- Counselor dashboard now prioritizes overdue, urgent, unassigned, and assigned case workload.
- Admin dashboard now prioritizes launch readiness, billing/commercial readiness, outbox health, and account hardening.

## Guardrails
- No teacher access to private journal text was added.
- No medical diagnosis wording was added.
- No production readiness is claimed when onboarding blockers or provider settings remain incomplete.
