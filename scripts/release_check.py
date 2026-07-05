import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_SUFFIXES = {".pyc", ".sqlite", ".sqlite3", ".db"}
BLOCKED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
REQUIRED_DOCS = [
    "docs/RELEASE_CHECKLIST.md",
    "docs/POSTGRESQL_MIGRATION_PLAN.md",
    "docs/BACKUP_RESTORE_RUNBOOK.md",
    "docs/PRODUCTION_RUNBOOK.md",
]
REQUIRED_FILES = [
    "app.py",
    "wsgi.py",
    "Procfile",
    "render.yaml",
    "requirements.txt",
    "schoolmind/templates/dashboard/database.html",
]

findings = []
for path in ROOT.rglob("*"):
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] == "instance":
        continue
    if any(part in BLOCKED_DIRS for part in rel.parts):
        findings.append(f"blocked runtime directory: {rel}")
        continue
    if path.is_file() and path.suffix.lower() in BLOCKED_SUFFIXES:
        findings.append(f"blocked runtime file: {rel}")

for item in REQUIRED_DOCS + REQUIRED_FILES:
    if not (ROOT / item).exists():
        findings.append(f"missing required release artifact: {item}")

css = (ROOT / "schoolmind/static/css/pixel.css").read_text(encoding="utf-8")
for marker in ["prefers-reduced-motion", "status-blocker", "@media (max-width: 420px)", "workspace-menu-btn", "personalization-panel"]:
    if marker not in css:
        findings.append(f"missing final mobile CSS marker: {marker}")

js = (ROOT / "schoolmind/static/js/app.js").read_text(encoding="utf-8")
for marker in ["aria-expanded", "Escape", "data-nour-chat", "X-CSRF-Token", "data-side-panel", "data-open-personalization"]:
    if marker not in js:
        findings.append(f"missing final JS marker: {marker}")

if findings:
    print("Release check failed:")
    for item in findings:
        print(f"- {item}")
    sys.exit(1)

print("Release check passed.")
