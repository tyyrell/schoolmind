from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
required = [
    "app.py",
    "wsgi.py",
    "requirements.txt",
    "Procfile",
    "render.yaml",
    "schoolmind/__init__.py",
    "schoolmind/db.py",
    "schoolmind/security.py",
    "schoolmind/services/validators.py",
    "schoolmind/static/css/pixel.css",
    "schoolmind/templates/dashboard/onboarding.html",
    "schoolmind/templates/dashboard/import.html",
    "schoolmind/templates/dashboard/settings.html",
    "schoolmind/templates/dashboard/consent.html",
    "schoolmind/templates/dashboard/playbooks.html",
    "schoolmind/templates/dashboard/invites.html",
    "schoolmind/templates/dashboard/reports.html",
    "schoolmind/templates/dashboard/outbox.html",
    "schoolmind/templates/dashboard/student.html",
    "schoolmind/templates/dashboard/teacher.html",
    "schoolmind/templates/dashboard/student_detail.html",
    "schoolmind/templates/dashboard/operations.html",
    "schoolmind/templates/dashboard/backups.html",
    "schoolmind/templates/dashboard/database.html",
    "schoolmind/services/database_ops.py",
    "docs/BACKUP_RESTORE_RUNBOOK.md",
    "docs/POSTGRESQL_MIGRATION_PLAN.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/PRODUCTION_RUNBOOK.md",
    "scripts/route_audit.py",
    "schoolmind/templates/auth/accept_invite.html",
    "schoolmind/templates/auth/forgot_password.html",
    "schoolmind/templates/auth/reset_password.html",
    "schoolmind/templates/platform/school.html",
    "schoolmind/templates/platform/home.html",
    "schoolmind/templates/platform/login.html",
    "schoolmind/templates/dashboard/security.html",
    "schoolmind/platform.py",
]
missing = [item for item in required if not (ROOT / item).exists()]
if missing:
    raise SystemExit(f"Missing files: {missing}")
css = (ROOT / "schoolmind/static/css/pixel.css").read_text(encoding="utf-8")
if "box-shadow" not in css or "--accent" not in css or "pixel-bg" not in css:
    raise SystemExit("Design system audit failed")
for marker in ["prefers-reduced-motion", "status-blocker", "@media (max-width: 420px)"]:
    if marker not in css:
        raise SystemExit(f"Missing final UI marker: {marker}")
source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "schoolmind").rglob("*.py"))
for marker in ["guardian_consent_required", "billing_events", "sales_leads", "import_batches", "playbooks", "invite_tokens", "outbox_messages", "password_reset_tokens", "case_actions", "agreement_acceptances", "wellbeing_assessments", "student_support_plans", "analyze_wellbeing_assessment", "support_plan_from_assessment", "BILLING_WEBHOOK_SECRET", "dispatch_queued", "platform_required", "platform_admins", "account_security_events", "admin_backups", "workspace_backup_downloaded", "ALLOW_DEMO_DATA_IN_PRODUCTION", "SCHEMA_VERSION", "database_runtime_report", "admin_database"]:
    if marker not in source:
        raise SystemExit(f"Missing SaaS marker: {marker}")
unsafe = []
safe_claim_markers = [
    "not a diagnosis",
    "does not diagnose",
    "not diagnose",
    "no diagnosis",
    "without diagnosis",
    "not a medical",
    "not medical",
    "not diagnostic",
    "not diagnosis",
    "non-diagnostic",
    "does not provide medical diagnosis",
    "does not make final decisions",
    "no_diagnosis",
]
for template in (ROOT / "schoolmind/templates").rglob("*.html"):
    text = template.read_text(encoding="utf-8")
    for match in re.finditer(r"diagnos(?:e|es|ed|ing|is|tic)", text, re.I):
        start = max(0, match.start() - 180)
        end = min(len(text), match.end() + 180)
        context = text[start:end].lower()
        if not any(marker in context for marker in safe_claim_markers):
            unsafe.append(f"{template.relative_to(ROOT)} near {match.group(0)!r}")
            break
if unsafe:
    raise SystemExit(f"Unsafe diagnosis language: {unsafe}")
print("Audit passed.")
