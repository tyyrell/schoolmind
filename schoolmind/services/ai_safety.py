"""AI safety language, boundaries, and user-facing copy for SchoolMind AI.

The application intentionally frames automated outputs as educational support
indicators. These constants are used by public pages, dashboard notices, audits,
and tests so future edits do not drift toward unsafe product claims.
"""

AI_SAFETY_PRINCIPLES = [
    {
        "title": "Educational indicators only",
        "body": "Automated outputs organize school support context; they are not medical, clinical, or disciplinary determinations.",
    },
    {
        "title": "Human review required",
        "body": "Authorized school staff must review signals, decide follow-up, and apply the school-approved support protocol.",
    },
    {
        "title": "Role-safe visibility",
        "body": "Teachers see aggregate patterns; counselors and admins receive only the context their role is permitted to handle.",
    },
    {
        "title": "Emergency boundary",
        "body": "SchoolMind AI is not an emergency service. Schools must maintain real-world escalation procedures outside the platform.",
    },
]

AI_SAFETY_DO_LIST = [
    "Use SchoolMind AI to structure check-ins, support requests, counselor queues, and school operations.",
    "Review every elevated signal through an authorized human support process.",
    "Explain privacy, consent, and review boundaries before real student data is used.",
    "Keep local school policies, guardianship rules, and emergency procedures outside the software as the source of truth.",
]

AI_SAFETY_DO_NOT_LIST = [
    "Do not market SchoolMind AI as diagnosis, therapy, medical scoring, or emergency response.",
    "Do not use automated labels as final decisions about a student.",
    "Do not give teachers private student writing or sensitive counselor-only context.",
    "Do not enable external AI processing of student text without legal, privacy, and school approval.",
]

# Terms that should not appear in marketing copy as promises/capabilities.
MARKETING_CLAIM_BLOCKLIST = [
    "diagnoses students",
    "diagnose students",
    "medical diagnosis engine",
    "therapy replacement",
    "replaces counselors",
    "replaces teachers",
    "emergency service",
    "guarantees prevention",
    "predicts mental illness",
    "detects mental illness",
]

SIGNAL_LEVEL_COPY = {
    "steady": {
        "label": "Steady indicator",
        "summary": "Current inputs do not require elevated platform routing. Keep the normal check-in routine visible.",
    },
    "watch": {
        "label": "Watch indicator",
        "summary": "Inputs suggest pressure may be building. A human reviewer should keep a light-touch follow-up visible.",
    },
    "support": {
        "label": "Support indicator",
        "summary": "Inputs suggest a support conversation may be useful. Route to the approved school support workflow.",
    },
    "urgent": {
        "label": "Urgent human-review indicator",
        "summary": "Inputs require prompt human review through the school's approved support path. This is not an automated decision.",
    },
}

PUBLIC_AI_SAFETY_STATEMENT = (
    "SchoolMind AI uses AI-assisted and rule-based educational indicators to help schools organize support workflows. "
    "It does not diagnose, treat, replace staff judgment, or operate as an emergency service."
)


def signal_level_label(level):
    """Return a safe public label for an internal signal level."""
    return SIGNAL_LEVEL_COPY.get(level, SIGNAL_LEVEL_COPY["steady"])["label"]


def signal_level_summary(level):
    """Return a safe public explanation for an internal signal level."""
    return SIGNAL_LEVEL_COPY.get(level, SIGNAL_LEVEL_COPY["steady"])["summary"]


def marketing_claim_violations(text):
    """Find risky marketing claims in supplied text.

    This is intentionally simple and deterministic so it can be used in CI/audit
    scripts without external services.
    """
    normalized = (text or "").lower()
    return [claim for claim in MARKETING_CLAIM_BLOCKLIST if claim in normalized]
