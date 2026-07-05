"""Role-specific dashboard command centers for SchoolMind workspaces.

The functions in this module keep the role dashboards from becoming generic
metric dumps. Each role receives a primary next action, a compact KPI strip,
and a role-safe workflow list. No function exposes private journal text to
roles that should not see it.
"""


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_student_command_center(snapshot, latest_assessment, active_plans, consent_ok, settings):
    score = _safe_int(snapshot.get("score", 0)) if isinstance(snapshot, dict) else 0
    level = (snapshot.get("level") if isinstance(snapshot, dict) else "steady") or "steady"
    plan_count = _safe_int(snapshot.get("plan_count", 0)) if isinstance(snapshot, dict) else 0
    checkin_count = _safe_int(snapshot.get("checkin_count", 0)) if isinstance(snapshot, dict) else 0
    journal_count = _safe_int(snapshot.get("journal_count", 0)) if isinstance(snapshot, dict) else 0

    if not consent_ok:
        title = "Student tools are waiting for consent."
        summary = "Your school requires recorded guardian consent before support tools unlock."
        primary_action = "Review help center"
        primary_endpoint = "dashboard.help_center"
        status = "locked"
    elif not latest_assessment:
        title = "Start with the two-minute support scan."
        summary = "Create a safer starting point before journals, Nour messages, or support requests pile up."
        primary_action = "Start on this page"
        primary_endpoint = "dashboard.student_home"
        status = "watch"
    elif level in {"support", "urgent"}:
        title = "Use the support plan before adding more noise."
        summary = "The latest signal suggests a human-reviewed next step, not a label or diagnosis."
        primary_action = "Open support plans"
        primary_endpoint = "dashboard.support_plans"
        status = level
    elif plan_count == 0:
        title = "Turn your check-in into a small plan."
        summary = "A plan makes the next step visible to you and your support workflow."
        primary_action = "Create a support plan"
        primary_endpoint = "dashboard.student_home"
        status = "watch"
    else:
        title = "Keep the routine small and consistent."
        summary = "Review progress, complete one practice activity, and update your plan when something changes."
        primary_action = "Open progress hub"
        primary_endpoint = "dashboard.progress_hub"
        status = "steady"

    return {
        "label": "Student command center",
        "title": title,
        "summary": summary,
        "status": status,
        "primary_action": primary_action,
        "primary_endpoint": primary_endpoint,
        "kpis": [
            {"label": "Score", "value": score, "detail": "Latest support indicator"},
            {"label": "Plans", "value": plan_count, "detail": "Active support steps"},
            {"label": "Inputs", "value": checkin_count + journal_count, "detail": "Recent check-ins and journals"},
            {"label": "Support owner", "value": settings["support_owner"] or "Team", "detail": "Human review path"},
        ],
        "actions": [
            {"title": "Update the scan", "body": "Refresh the two-minute support scan when your week changes.", "endpoint": "dashboard.student_home"},
            {"title": "Write privately", "body": "Use the journal for reflection inside the support workflow.", "endpoint": "dashboard.journal_studio"},
            {"title": "Ask Nour", "body": "Get a small next step with human-routing boundaries.", "endpoint": "dashboard.companion_studio"},
            {"title": "Track progress", "body": "See goals, practice, breathing, and summaries together.", "endpoint": "dashboard.progress_hub"},
        ],
    }


def build_teacher_command_center(assessment_rows, practice_rows, requests_count, group_name):
    groups = [row for row in assessment_rows if row["group_name"] or row["students"]]
    total_students = sum(_safe_int(row["students"]) for row in assessment_rows)
    avg_scores = [_safe_float(row["avg_score"]) for row in assessment_rows if row["avg_score"] is not None]
    avg_score = round(sum(avg_scores) / len(avg_scores), 1) if avg_scores else "—"
    watch_groups = sum(
        1
        for row in assessment_rows
        if row["avg_score"] is not None and (_safe_float(row["avg_score"]) < 70 or _safe_float(row["avg_stress"]) >= 4)
    )
    practice_sessions = sum(_safe_int(row["game_sessions"]) + _safe_int(row["breathing_sessions"]) for row in practice_rows)

    if not groups:
        title = "No class group is assigned yet."
        summary = "Ask an administrator to assign students to your group before the classroom pulse is useful."
        primary_action = "Open help center"
        primary_endpoint = "dashboard.help_center"
        status = "watch"
    elif watch_groups:
        title = "Adjust the classroom before individual pressure escalates."
        summary = "Use aggregate pulse data for workload, pacing, and classroom climate; do not label students."
        primary_action = "Review class moves"
        primary_endpoint = "dashboard.teacher_home"
        status = "support"
    else:
        title = "Class pulse is stable. Keep the rhythm visible."
        summary = "Maintain low-friction check-ins and use aggregate patterns for classroom decisions."
        primary_action = "Open activity center"
        primary_endpoint = "dashboard.activity_center"
        status = "steady"

    group_label = group_name or "All assigned"
    return {
        "label": "Teacher command center",
        "title": title,
        "summary": summary,
        "status": status,
        "primary_action": primary_action,
        "primary_endpoint": primary_endpoint,
        "kpis": [
            {"label": "Scope", "value": group_label, "detail": "Visible group"},
            {"label": "Students", "value": total_students, "detail": "Aggregate only"},
            {"label": "Average score", "value": avg_score, "detail": "Latest scans"},
            {"label": "Support requests", "value": requests_count, "detail": "Routed to support team"},
        ],
        "actions": [
            {"title": "Review class pulse", "body": "Use score, stress, sleep, and belonging patterns at group level.", "endpoint": "dashboard.teacher_home"},
            {"title": "Check activity", "body": "Track classroom-level scan movement without private journals.", "endpoint": "dashboard.activity_center"},
            {"title": "Use help guidance", "body": "Reconfirm what teachers can and cannot see.", "endpoint": "dashboard.help_center"},
            {"title": "Encourage practice", "body": "Suggest low-pressure activities instead of student labeling.", "endpoint": "dashboard.teacher_home"},
        ],
        "privacy_notes": [
            "No private journal text is displayed.",
            "No individual diagnosis or mental-health label is shown.",
            "Counselor workflows handle sensitive follow-up.",
        ],
    }


def build_counselor_command_center(alerts, requests, focus_rows, overdue_count, settings, current_user_id):
    open_alerts = len(alerts)
    urgent_alerts = sum(1 for alert in alerts if alert["risk_level"] == "urgent")
    support_alerts = sum(1 for alert in alerts if alert["risk_level"] == "support")
    unassigned = sum(1 for alert in alerts if not alert["assigned_to"])
    assigned_to_me = sum(1 for alert in alerts if alert["assigned_to"] == current_user_id)
    review_focus = sum(1 for row in focus_rows if row["risk_level"] in {"support", "urgent"})

    if overdue_count:
        title = "SLA breach risk: review overdue alerts first."
        summary = f"{overdue_count} alert(s) are beyond the {settings['escalation_window_minutes']} minute escalation window."
        primary_action = "Review open alerts"
        primary_endpoint = "dashboard.counselor_home"
        status = "urgent"
    elif urgent_alerts:
        title = "Urgent support signals need ownership."
        summary = "Assign or escalate urgent items before reviewing lower-priority queues."
        primary_action = "Open counselor queue"
        primary_endpoint = "dashboard.counselor_home"
        status = "urgent"
    elif unassigned:
        title = "Assign ownership before cases drift."
        summary = "Unassigned cases create accountability gaps; claim or route the first queue item."
        primary_action = "Assign first case"
        primary_endpoint = "dashboard.counselor_home"
        status = "support"
    else:
        title = "Queue is under control. Move to follow-up quality."
        summary = "Review focus rows, update support plans, and keep notes short and actionable."
        primary_action = "Open reports"
        primary_endpoint = "dashboard.reports"
        status = "steady"

    return {
        "label": "Counselor command center",
        "title": title,
        "summary": summary,
        "status": status,
        "primary_action": primary_action,
        "primary_endpoint": primary_endpoint,
        "kpis": [
            {"label": "Open alerts", "value": open_alerts, "detail": f"{urgent_alerts} urgent · {support_alerts} support"},
            {"label": "Overdue", "value": overdue_count, "detail": f"SLA {settings['escalation_window_minutes']} min"},
            {"label": "Unassigned", "value": unassigned, "detail": "Needs owner"},
            {"label": "Assigned to me", "value": assigned_to_me, "detail": "Current active load"},
        ],
        "actions": [
            {"title": "Triage queue", "body": "Assign, escalate, or close alerts with short notes.", "endpoint": "dashboard.counselor_home"},
            {"title": "Review focus students", "body": f"{review_focus} student(s) currently show support or urgent scan focus.", "endpoint": "dashboard.counselor_home"},
            {"title": "Manage playbooks", "body": "Keep response steps consistent across counselor staff.", "endpoint": "dashboard.counselor_playbooks"},
            {"title": "Review reports", "body": "Use group and need patterns for supervised support planning.", "endpoint": "dashboard.reports"},
        ],
    }


def build_admin_command_center(counts, onboarding_state, subscription, outbox, settings):
    readiness = onboarding_state.get("score", 0)
    blockers = len(onboarding_state.get("blockers", []))
    queued = _safe_int(outbox["queued"] if outbox else 0)
    failed = _safe_int(outbox["failed"] if outbox else 0)
    status = "steady"
    title = "Workspace is ready for controlled operation."
    summary = "Keep monitoring billing, consent, email, security, and support workflow readiness."
    primary_action = "Open operations center"
    primary_endpoint = "dashboard.admin_operations"

    if blockers:
        status = "support"
        title = "Launch blockers remain. Do not present this as production-ready."
        summary = "Finish onboarding blockers before importing real student data or starting a paid rollout."
        primary_action = "Fix launch checklist"
        primary_endpoint = "dashboard.onboarding"
    elif failed:
        status = "urgent"
        title = "Email failures need attention before outreach."
        summary = "Failed transactional messages can break invites, demos, and reset flows."
        primary_action = "Open outbox"
        primary_endpoint = "dashboard.admin_outbox"
    elif not subscription:
        status = "watch"
        title = "Commercial state is not connected yet."
        summary = "Billing can show plans, but provider checkout and webhook configuration still matter before production."
        primary_action = "Open billing"
        primary_endpoint = "dashboard.admin_billing"

    return {
        "label": "Admin command center",
        "title": title,
        "summary": summary,
        "status": status,
        "primary_action": primary_action,
        "primary_endpoint": primary_endpoint,
        "kpis": [
            {"label": "Launch readiness", "value": f"{readiness}%", "detail": f"{blockers} blocker(s)"},
            {"label": "Students", "value": counts["students"], "detail": "Roster size"},
            {"label": "Open events", "value": counts["open_events"], "detail": "Needs workflow monitoring"},
            {"label": "Outbox", "value": queued + failed, "detail": f"{queued} queued · {failed} failed"},
        ],
        "actions": [
            {"title": "Finish launch readiness", "body": "Complete governance, privacy, staff, roster, and billing setup.", "endpoint": "dashboard.onboarding"},
            {"title": "Review operations", "body": "Check production config, plan usage, outbox, and escalation health.", "endpoint": "dashboard.admin_operations"},
            {"title": "Inspect billing", "body": "Confirm checkout URLs, annual/monthly cycles, and trial boundaries.", "endpoint": "dashboard.admin_billing"},
            {"title": "Harden accounts", "body": "Review lockouts, reset links, and account security events.", "endpoint": "dashboard.admin_security"},
        ],
        "governance": [
            {"label": "Support owner", "value": settings["support_owner"] or "Missing"},
            {"label": "Data owner", "value": settings["data_owner"] or "Missing"},
            {"label": "Launch mode", "value": settings["launch_mode"]},
        ],
    }
