# Phase 10 — AI Safety and Claim Control

## Goal
Keep SchoolMind AI positioned as an AI-assisted educational support platform, not a clinical, therapy, emergency, or automated decision product.

## Implemented
- Added `schoolmind/services/ai_safety.py` as the single source for AI safety principles, public safety copy, unsafe marketing claim detection, and safe signal-level explanations.
- Rebuilt `/safety` and added `/ai-safety` as an alias.
- Added a reusable dashboard partial: `partials/ai_safety_notice.html`.
- Added AI safety notices to student, Nour companion, counselor, and reports surfaces.
- Updated analyzer summaries and Nour replies to use safer human-review wording.
- Added `scripts/ai_safety_audit.py` to prevent deletion of safety controls or reintroduction of blocked claims.
- Updated documentation wording from detection-style claims to organize/routing language where appropriate.

## Guardrails
- No diagnosis claims.
- No therapy or emergency-service positioning.
- No automated final decisions.
- No teacher access to private journal text.
- No external AI processing of student text unless future legal/privacy approval exists.
