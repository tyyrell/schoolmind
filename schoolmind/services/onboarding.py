"""School launch onboarding helpers.

The checklist is intentionally operational, not decorative. It keeps new school
admins focused on governance, people, consent, students, billing, and safety
before they treat the workspace as production-ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LaunchTask:
    key: str
    category: str
    title: str
    summary: str
    action_label: str
    endpoint: str
    blocker: bool = True


LAUNCH_TASKS = (
    LaunchTask(
        "profile",
        "School profile",
        "Complete the launch profile",
        "Set country, launch mode, expected students, approval owner, data owner, and support inbox.",
        "Complete launch profile",
        "dashboard.onboarding",
    ),
    LaunchTask(
        "policy",
        "Governance",
        "Set school policy and data retention",
        "Define support owner, escalation window, guardian consent requirement, retention, and human escalation instructions.",
        "Open policy settings",
        "dashboard.admin_settings",
    ),
    LaunchTask(
        "billing",
        "Commercial readiness",
        "Choose trial, monthly, annual, or guided pilot billing",
        "A subscription record or checkout path must exist before the workspace is presented as commercially ready.",
        "Review billing",
        "dashboard.admin_billing",
    ),
    LaunchTask(
        "consent",
        "Privacy",
        "Record consent readiness",
        "If guardian consent is required, at least one consent record should exist before real student data is used.",
        "Open consent center",
        "dashboard.admin_consent",
    ),
    LaunchTask(
        "staff",
        "People",
        "Create teacher and counselor accounts",
        "A school launch is fake if there is no teacher and no counselor workflow owner.",
        "Invite staff",
        "dashboard.admin_invites",
    ),
    LaunchTask(
        "students",
        "Roster",
        "Import or create student accounts",
        "The workspace needs a controlled roster import before any real school evaluation.",
        "Import users",
        "dashboard.admin_import",
    ),
    LaunchTask(
        "protocol",
        "Safety",
        "Review the human escalation protocol",
        "The workspace must show clear emergency instructions and an escalation window greater than zero.",
        "Review operations",
        "dashboard.admin_operations",
    ),
)


def _truthy_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def build_onboarding_state(settings, counts, subscription, consent_count=0, invite_count=0, import_count=0):
    """Return a structured launch-readiness model for dashboard rendering and tests."""
    completed = {
        "profile": all(
            [
                _truthy_text(settings["approval_owner"] if "approval_owner" in settings.keys() else ""),
                _truthy_text(settings["data_owner"] if "data_owner" in settings.keys() else ""),
                _truthy_text(settings["support_email"] if "support_email" in settings.keys() else ""),
                _positive_int(settings["expected_students"] if "expected_students" in settings.keys() else 0),
            ]
        ),
        "policy": _truthy_text(settings["support_owner"]) and _truthy_text(settings["emergency_instructions"]),
        "billing": bool(subscription),
        "consent": consent_count > 0 or int(settings["guardian_consent_required"] or 0) == 0,
        "staff": counts["counselors"] > 0 and counts["teachers"] > 0,
        "students": counts["students"] > 0,
        "protocol": int(settings["escalation_window_minutes"] or 0) > 0 and _truthy_text(settings["emergency_instructions"]),
    }
    done = sum(1 for task in LAUNCH_TASKS if completed.get(task.key))
    total = len(LAUNCH_TASKS)
    percent = round((done / total) * 100) if total else 0
    blockers = [task for task in LAUNCH_TASKS if task.blocker and not completed.get(task.key)]
    next_task = blockers[0] if blockers else None
    readiness = "ready" if done == total else "needs_work" if done >= max(1, total // 2) else "not_ready"
    launch_mode = settings["launch_mode"] if "launch_mode" in settings.keys() else "self_serve_trial"
    launch_stage = settings["launch_stage"] if "launch_stage" in settings.keys() else "setup"
    return {
        "tasks": LAUNCH_TASKS,
        "completed": completed,
        "done": done,
        "total": total,
        "percent": percent,
        "blockers": blockers,
        "next_task": next_task,
        "readiness": readiness,
        "launch_mode": launch_mode,
        "launch_stage": launch_stage,
        "invite_count": int(invite_count or 0),
        "import_count": int(import_count or 0),
        "can_mark_ready": done == total,
    }
