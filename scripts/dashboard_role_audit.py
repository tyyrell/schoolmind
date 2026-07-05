#!/usr/bin/env python3
"""Audit Phase 09 role-specific dashboard command centers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ROOT / "schoolmind" / "services" / "role_dashboards.py",
    ROOT / "schoolmind" / "templates" / "partials" / "role_command_center.html",
]

ROLE_TEMPLATES = {
    "student": ROOT / "schoolmind" / "templates" / "dashboard" / "student.html",
    "teacher": ROOT / "schoolmind" / "templates" / "dashboard" / "teacher.html",
    "counselor": ROOT / "schoolmind" / "templates" / "dashboard" / "counselor.html",
    "admin": ROOT / "schoolmind" / "templates" / "dashboard" / "admin.html",
}

SERVICE_MARKERS = [
    "build_student_command_center",
    "build_teacher_command_center",
    "build_counselor_command_center",
    "build_admin_command_center",
    "No private journal text is displayed.",
    "Do not present this as production-ready.",
]

CSS_MARKERS = [
    ".role-command-center",
    ".role-workflow-grid",
    ".role-note-grid",
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    for path in REQUIRED_FILES:
        require(path.exists(), f"Missing required Phase 09 file: {path}")

    service_text = (ROOT / "schoolmind" / "services" / "role_dashboards.py").read_text(encoding="utf-8")
    for marker in SERVICE_MARKERS:
        require(marker in service_text, f"Missing service marker: {marker}")

    partial_text = (ROOT / "schoolmind" / "templates" / "partials" / "role_command_center.html").read_text(encoding="utf-8")
    require("role_board.primary_endpoint" in partial_text, "Role command partial must expose primary action endpoint")
    require("role_board.kpis" in partial_text, "Role command partial must render KPI cards")
    require("role_board.actions" in partial_text, "Role command partial must render workflow actions")

    for role, path in ROLE_TEMPLATES.items():
        text = path.read_text(encoding="utf-8")
        require("partials/role_command_center.html" in text, f"{role} dashboard does not include role command center")

    dashboard_text = (ROOT / "schoolmind" / "dashboard.py").read_text(encoding="utf-8")
    for marker in SERVICE_MARKERS[:4]:
        require(marker in dashboard_text, f"dashboard.py does not call {marker}")

    css_text = (ROOT / "schoolmind" / "static" / "css" / "company.css").read_text(encoding="utf-8")
    for marker in CSS_MARKERS:
        require(marker in css_text, f"Missing CSS marker: {marker}")

    print("Dashboard role audit passed")


if __name__ == "__main__":
    main()
