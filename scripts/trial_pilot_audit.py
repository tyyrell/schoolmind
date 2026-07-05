#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "schoolmind/templates/public/trial.html": [
        "Self-serve evaluation trial",
        "Pick the right path",
        "Start Standard trial",
        "Request guided pilot",
        "No fake free plan",
    ],
    "schoolmind/templates/public/pilot.html": [
        "Guided pilot",
        "lead_type",
        "guided_pilot",
        "privacy_review_needed",
        "student_count",
    ],
    "schoolmind/templates/public/request_demo.html": [
        "lead_type",
        "student_count",
        "preferred_path",
        "requested_plan",
        "billing_cycle",
    ],
    "schoolmind/templates/auth/start.html": [
        "accept_human_review",
        "accept_trial_boundary",
        "Plan guided pilot",
        "30-day evaluation trial",
    ],
    "schoolmind/public.py": [
        "def trial()",
        "normalize_sales_lead",
        "queue_sales_lead_notification",
        "privacy_review_needed",
    ],
    "schoolmind/db.py": [
        "lead_type TEXT NOT NULL DEFAULT 'contact'",
        "student_count INTEGER NOT NULL DEFAULT 0",
        "idx_leads_type_status",
    ],
}

missing = []
for rel, needles in checks.items():
    text = (ROOT / rel).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            missing.append(f"{rel}: missing {needle}")

if missing:
    raise SystemExit("\n".join(missing))

print("Trial/pilot audit passed")
