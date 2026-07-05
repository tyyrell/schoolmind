#!/usr/bin/env python3
"""Phase 8 audit: verifies school launch onboarding is real, not a static page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = [
    (ROOT / "schoolmind" / "services" / "onboarding.py", ["LAUNCH_TASKS", "build_onboarding_state", "can_mark_ready"]),
    (ROOT / "schoolmind" / "templates" / "dashboard" / "onboarding.html", ["School launch onboarding", "Launch profile", "Operational launch checklist", "mark_ready", "reset_launch"]),
    (ROOT / "schoolmind" / "dashboard.py", ["methods=(\"GET\", \"POST\")", "onboarding_profile_updated", "onboarding_marked_ready", "onboarding_reset"]),
    (ROOT / "schoolmind" / "db.py", ["launch_language", "launch_mode", "approval_owner", "data_owner", "support_email", "expected_students", "onboarding_completed_at"]),
    (ROOT / "schoolmind" / "static" / "css" / "company.css", ["Phase 8: school onboarding workspace", "launch-score-card", "launch-checklist", "launch-profile-form"]),
]

missing = []
for path, needles in checks:
    if not path.exists():
        missing.append(f"Missing file: {path.relative_to(ROOT)}")
        continue
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            missing.append(f"Missing {needle!r} in {path.relative_to(ROOT)}")

if missing:
    for item in missing:
        print(item)
    raise SystemExit(1)
print("Onboarding audit passed")
