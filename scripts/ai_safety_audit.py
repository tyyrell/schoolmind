from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "schoolmind/services/ai_safety.py",
    "schoolmind/templates/public/safety.html",
    "schoolmind/templates/public/human_review.html",
    "schoolmind/templates/partials/ai_safety_notice.html",
]
REQUIRED_MARKERS = {
    "schoolmind/services/ai_safety.py": [
        "AI_SAFETY_PRINCIPLES",
        "MARKETING_CLAIM_BLOCKLIST",
        "marketing_claim_violations",
        "Emergency boundary",
    ],
    "schoolmind/templates/public/safety.html": [
        "AI-assisted does not mean AI-controlled",
        "Operating boundaries",
        "Allowed use",
        "Not allowed",
        "Signal routing",
    ],
    "schoolmind/templates/partials/ai_safety_notice.html": [
        "AI safety boundary",
        "Educational indicators",
        "does not diagnose",
    ],
    "schoolmind/templates/dashboard/companion.html": [
        "Nour safety boundary",
        "make final support decisions",
    ],
    "schoolmind/templates/dashboard/student.html": [
        "Student safety boundary",
    ],
    "schoolmind/templates/dashboard/counselor.html": [
        "Counselor review boundary",
    ],
    "schoolmind/templates/dashboard/reports.html": [
        "Reports safety boundary",
    ],
    "schoolmind/static/css/company.css": [
        ".ai-safety-notice",
        ".ai-boundary-card",
    ],
}
BLOCKED_MARKETING = [
    "diagnoses students",
    "therapy replacement",
    "replaces counselors",
    "predicts mental illness",
    "detects mental illness",
]
SCAN_PATHS = ["schoolmind/templates/public", "README.md", "docs"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def main():
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        print("Missing AI safety files:", missing)
        return 1
    for rel, needles in REQUIRED_MARKERS.items():
        text = read(rel)
        for needle in needles:
            if needle not in text:
                print(f"Missing marker {needle!r} in {rel}")
                return 1
    for scan in SCAN_PATHS:
        path = ROOT / scan
        files = [path] if path.is_file() else list(path.rglob("*.html")) + list(path.rglob("*.md"))
        for file in files:
            text = file.read_text(encoding="utf-8", errors="ignore").lower()
            for claim in BLOCKED_MARKETING:
                if claim in text:
                    print(f"Blocked marketing claim {claim!r} found in {file.relative_to(ROOT)}")
                    return 1
    print("AI safety audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
