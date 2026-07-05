# Phase 07 — Trial and Guided Pilot System

## Goal

Turn the public conversion path into a safer SaaS funnel with three clearly separated paths:

1. Instant limited demo for exploration before registration.
2. 30-day self-serve trial for supervised platform evaluation.
3. Guided pilot for larger or higher-governance schools.

## Implemented

- Added `/trial` as the decision page between instant demo, self-serve trial, and guided pilot.
- Expanded `/pilot` into a serious pilot planning page with a structured request form.
- Expanded `/request-demo` with student count, likely plan, billing cycle, and preferred path fields.
- Extended `sales_leads` with lead classification and qualification fields:
  - `lead_type`
  - `requested_plan`
  - `billing_cycle`
  - `student_count`
  - `launch_timeline`
  - `preferred_path`
  - `role_interest`
  - `privacy_review_needed`
- Added migration coverage for existing databases through `ensure_columns`.
- Queued internal lead notifications in `outbox_messages` so leads do not silently disappear.
- Added stricter trial acknowledgements before workspace creation:
  - platform terms/privacy commitments
  - mandatory human review
  - supervised evaluation and data-governance boundary
- Removed self-serve custom/scale workspace creation from the trial form. Large deployments are routed to guided pilot.

## Product Guardrail

The 30-day trial is described as evaluation access, not a permanent free plan and not permission to collect uncontrolled production student data.

## Remaining Production Inputs

- Connect a real email provider so queued lead notifications are delivered.
- Decide final custom/pilot commercial terms for schools above 1,000 students.
- Review legal language before onboarding real students.
