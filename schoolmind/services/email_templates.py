from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flask import current_app


@dataclass(frozen=True)
class EmailTemplate:
    key: str
    subject: str
    body: str


PRODUCT_NAME = "SchoolMind AI"


TEMPLATES: dict[str, EmailTemplate] = {
    "workspace_invite": EmailTemplate(
        key="workspace_invite",
        subject="SchoolMind AI workspace invite",
        body=(
            "Hello,\n\n"
            "You were invited to join {school_name} on SchoolMind AI.\n\n"
            "Open this secure invite link within 7 days:\n{invite_url}\n\n"
            "SchoolMind AI is used for supervised school support workflows. It does not replace human review, emergency services, or professional judgment.\n\n"
            "— SchoolMind AI"
        ),
    ),
    "password_reset": EmailTemplate(
        key="password_reset",
        subject="Reset your SchoolMind AI password",
        body=(
            "Hello,\n\n"
            "Use this password reset link within 2 hours:\n{reset_url}\n\n"
            "Ignore this message if you did not request a reset.\n\n"
            "— SchoolMind AI"
        ),
    ),
    "sales_lead_notification": EmailTemplate(
        key="sales_lead_notification",
        subject="SchoolMind AI {lead_type} lead · {school_name_or_name}",
        body=(
            "New SchoolMind AI lead captured.\n\n"
            "Lead type: {lead_type}\n"
            "Name: {name}\n"
            "Email: {email}\n"
            "School: {school_name}\n"
            "Requested plan: {requested_plan}\n"
            "Billing cycle: {billing_cycle}\n"
            "Student count: {student_count}\n"
            "Preferred path: {preferred_path}\n"
            "Timeline: {launch_timeline}\n"
            "Role interest: {role_interest}\n"
            "Privacy review needed: {privacy_review_needed}\n\n"
            "Message:\n{message}\n"
        ),
    ),
    "trial_started": EmailTemplate(
        key="trial_started",
        subject="Your SchoolMind AI 30-day trial is ready",
        body=(
            "Hello {admin_name},\n\n"
            "Your SchoolMind AI trial workspace for {school_name} is ready.\n\n"
            "Next steps:\n"
            "1. Complete the launch checklist.\n"
            "2. Confirm school governance and consent responsibilities.\n"
            "3. Invite staff only after your school is ready to use real data.\n\n"
            "Open workspace: {workspace_url}\n\n"
            "SchoolMind AI provides educational support indicators for supervised human review. It does not diagnose, treat, or replace emergency procedures.\n\n"
            "— SchoolMind AI"
        ),
    ),
    "test_email": EmailTemplate(
        key="test_email",
        subject="SchoolMind AI email test",
        body=(
            "This is a SchoolMind AI email delivery test.\n\n"
            "If this message was delivered by SMTP, transactional email is configured for this environment.\n"
            "If it appears only in console or outbox mode, production delivery is not complete yet.\n"
        ),
    ),
}


def render_email(template_key: str, context: Mapping[str, object] | None = None) -> tuple[str, str]:
    template = TEMPLATES.get(template_key)
    if not template:
        raise KeyError(f"Unknown email template: {template_key}")
    payload = SafeEmailContext(context or {})
    return template.subject.format_map(payload), template.body.format_map(payload)


class SafeEmailContext(dict):
    def __missing__(self, key):
        return ""


def workspace_url(path: str = "/") -> str:
    base = str(current_app.config.get("PUBLIC_BASE_URL", "http://localhost:5000")).rstrip("/")
    clean_path = "/" + str(path or "/").lstrip("/")
    return base + clean_path


def required_transactional_templates() -> tuple[str, ...]:
    return (
        "workspace_invite",
        "password_reset",
        "sales_lead_notification",
        "trial_started",
        "test_email",
    )
