import csv
import io
from datetime import UTC, datetime, timedelta
from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .config import ONBOARDING_TASKS, PLANS, ROLES
from .decorators import login_required, role_required, same_school_user
from .db import count_users, ensure_school_settings, ensure_user_preferences, execute, log_event, query_all, query_one, transaction, utcnow
from .i18n import FONT_SIZES, SUPPORTED_LANGUAGES, SUPPORTED_THEMES, normalize_language, normalize_theme
from .security import rate_limit, require_csrf, safe_referrer_redirect
from .services.analyzer import (
    analyze_student_signal,
    analyze_wellbeing_assessment,
    build_case_brief,
    build_student_snapshot,
    class_intervention_suggestions,
    companion_reply,
    support_plan_from_assessment,
)
from .services.mailer import dispatch_queued, email_delivery_health, latest_outbox_messages, queue_email, queue_template_email, queue_test_email
from .services.tokens import new_token
from .services.billing import activate_subscription_with_coupon, can_add_role, checkout_url_for, feature_limits, normalize_billing_cycle, plan_price, preview_coupon, pricing_catalog, seats_for_plan
from .services.validators import clean_text, normalize_email, valid_email
from .services.database_ops import database_runtime_report, database_table_counts, release_safety_checks
from .services.onboarding import build_onboarding_state
from .services.role_dashboards import (
    build_admin_command_center,
    build_counselor_command_center,
    build_student_command_center,
    build_teacher_command_center,
)

bp = Blueprint("dashboard", __name__)

DEMO_ALLOWED_POST_ENDPOINTS = {
    "dashboard.account_settings",
    "dashboard.student_checkin",
    "dashboard.student_assessment",
    "dashboard.student_journal",
    "dashboard.student_support",
    "dashboard.student_companion",
    "dashboard.journal_studio",
    "dashboard.companion_studio",
    "dashboard.nour_messages_api",
    "dashboard.student_goals",
    "dashboard.games",
    "dashboard.breathing_center",
}


@bp.before_request
def enforce_guided_demo_limits():
    if session.get("experience_mode") != "guided_demo":
        return None
    if request.method == "GET":
        session["demo_view_count"] = int(session.get("demo_view_count", 0) or 0) + 1
        if session["demo_view_count"] in {4, 8, 12} and not request.path.startswith("/static"):
            flash("You can keep exploring in demo mode, but a real workspace is required to save school data, invite staff, import students, export records, or activate billing.", "success")
        return None
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.endpoint in DEMO_ALLOWED_POST_ENDPOINTS:
        return None
    session["demo_locked_actions"] = int(session.get("demo_locked_actions", 0) or 0) + 1
    flash("This action is locked in the limited demo. Create a real workspace to invite users, import data, change billing, export records, or run administrator operations.", "error")
    return safe_referrer_redirect("dashboard.app_home")


@bp.route("/app")
@login_required
def app_home():
    role = g.user["role"]
    if role == "student":
        return redirect(url_for("dashboard.student_home"))
    if role == "teacher":
        return redirect(url_for("dashboard.teacher_home"))
    if role == "counselor":
        return redirect(url_for("dashboard.counselor_home"))
    return redirect(url_for("dashboard.onboarding"))


@bp.route("/help")
@login_required
def help_center():
    role = g.user["role"]
    cards = [
        {"title": "Start with the dashboard", "body": "Use the first page for the most important next actions for your role."},
        {"title": "Keep support human", "body": "SchoolMind organizes educational signals and workflows; school staff make support decisions."},
        {"title": "Use settings first", "body": "Personalize language, theme, accessibility, notifications, and security before demos or pilots."},
    ]
    if role == "student":
        cards.extend([
            {"title": "Student support journey", "body": "Check in, use Nour, complete a skill activity, then review progress or support plans."},
            {"title": "Privacy boundaries", "body": "Teachers see aggregate class pulse, not private journal text."},
        ])
    elif role == "teacher":
        cards.append({"title": "Class pulse", "body": "Use aggregate class indicators to adjust workload, check-ins, and classroom support."})
    elif role == "counselor":
        cards.append({"title": "Case timeline", "body": "Use the counselor hub and student detail views to assign, escalate, close, and document actions."})
    elif role == "admin":
        cards.extend([
            {"title": "School onboarding", "body": "Use the launch checklist, consent center, invites, billing, and database readiness screens before a pilot."},
            {"title": "Operational readiness", "body": "Review backups, retention, outbox, security, and plan limits before presenting to a customer."},
        ])
    return render_template("dashboard/help.html", cards=cards)


@bp.route("/activity")
@login_required
def activity_center():
    role = g.user["role"]
    if role == "student":
        items = query_all(
            """
            SELECT 'Check-in' AS type, risk_level AS status, created_at, note AS detail FROM checkins WHERE student_id = ?
            UNION ALL
            SELECT 'Game', CAST(score AS TEXT), created_at, game_name FROM game_scores WHERE student_id = ?
            UNION ALL
            SELECT 'Breathing', technique, created_at, CAST(duration_seconds AS TEXT) || ' seconds' FROM breathing_sessions WHERE student_id = ?
            UNION ALL
            SELECT 'Nour', risk_level, created_at, 'Message saved' FROM student_ai_messages WHERE student_id = ? AND role = 'student'
            ORDER BY created_at DESC LIMIT 30
            """,
            (g.user["id"], g.user["id"], g.user["id"], g.user["id"]),
        )
    elif role in {"counselor", "admin"}:
        items = query_all(
            """
            SELECT 'Risk event' AS type, risk_level AS status, created_at, title AS detail FROM risk_events WHERE school_id = ?
            UNION ALL
            SELECT 'Case action', action, created_at, note FROM case_actions WHERE school_id = ?
            UNION ALL
            SELECT 'Audit', action, created_at, detail FROM audit_events WHERE school_id = ?
            ORDER BY created_at DESC LIMIT 40
            """,
            (g.user["school_id"], g.user["school_id"], g.user["school_id"]),
        )
    elif role == "teacher":
        items = query_all(
            """
            SELECT 'Class scan' AS type, risk_level AS status, wellbeing_assessments.created_at, users.group_name AS detail
            FROM wellbeing_assessments
            JOIN users ON users.id = wellbeing_assessments.student_id
            WHERE wellbeing_assessments.school_id = ? AND users.group_name = ?
            ORDER BY wellbeing_assessments.created_at DESC LIMIT 30
            """,
            (g.user["school_id"], g.user["group_name"]),
        )
    else:
        items = query_all("SELECT 'Audit' AS type, action AS status, created_at, detail FROM audit_events WHERE school_id = ? ORDER BY created_at DESC LIMIT 30", (g.user["school_id"],))
    return render_template("dashboard/activity.html", items=items)


@bp.route("/settings/account", methods=("GET", "POST"))
@login_required
@require_csrf
def account_settings():
    preferences = ensure_user_preferences(g.user["id"])
    if request.method == "POST":
        action = request.form.get("action", "preferences")
        if action == "profile":
            name = clean_text(request.form.get("name"), 120)
            if len(name) < 2:
                flash("A display name is required.", "error")
                return redirect(url_for("dashboard.account_settings"))
            execute("UPDATE users SET name = ? WHERE id = ? AND school_id = ?", (name, g.user["id"], g.user["school_id"]))
            log_event("account_profile_updated", "User updated display name", school_id=g.user["school_id"], user_id=g.user["id"])
            flash("Profile saved.", "success")
        elif action == "preferences":
            language = normalize_language(request.form.get("language"))
            theme = normalize_theme(request.form.get("theme"))
            font_size = request.form.get("font_size") if request.form.get("font_size") in FONT_SIZES else "normal"
            execute(
                """
                UPDATE user_preferences
                SET language = ?, theme = ?, font_size = ?, reduced_motion = ?, high_contrast = ?, dyslexia_friendly = ?,
                    personalization_completed = 1, personalization_dismissed = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    language,
                    theme,
                    font_size,
                    checkbox_int("reduced_motion"),
                    checkbox_int("high_contrast"),
                    checkbox_int("dyslexia_friendly"),
                    utcnow(),
                    g.user["id"],
                ),
            )
            log_event("account_preferences_updated", f"Language {language}, theme {theme}", school_id=g.user["school_id"], user_id=g.user["id"])
            flash("Settings saved.", "success")
        elif action == "notifications":
            execute(
                """
                UPDATE user_preferences
                SET notify_email = ?, notify_support = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (checkbox_int("notify_email"), checkbox_int("notify_support"), utcnow(), g.user["id"]),
            )
            flash("Notification settings saved.", "success")
        elif action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not check_password_hash(g.user["password_hash"], current_password) or len(new_password) < 8:
                flash("Current password or new password is invalid.", "error")
                return redirect(url_for("dashboard.account_settings"))
            execute(
                "UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ? AND school_id = ?",
                (generate_password_hash(new_password), utcnow(), g.user["id"], g.user["school_id"]),
            )
            execute(
                """
                INSERT INTO account_security_events (school_id, user_id, email, event_type, success, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (g.user["school_id"], g.user["id"], g.user["email"], "password_changed", 1, "User changed password from account settings", utcnow()),
            )
            flash("Password updated.", "success")
        else:
            abort(400)
        return redirect(url_for("dashboard.account_settings"))
    preferences = ensure_user_preferences(g.user["id"])
    return render_template(
        "dashboard/account_settings.html",
        preferences=preferences,
        languages=SUPPORTED_LANGUAGES,
        themes=SUPPORTED_THEMES,
        font_sizes=FONT_SIZES,
    )


@bp.route("/student")
@role_required("student")
def student_home():
    journals = query_all(
        "SELECT * FROM journal_entries WHERE student_id = ? ORDER BY created_at DESC LIMIT 5",
        (g.user["id"],),
    )
    checkins = query_all(
        "SELECT * FROM checkins WHERE student_id = ? ORDER BY created_at DESC LIMIT 7",
        (g.user["id"],),
    )
    requests = query_all(
        "SELECT * FROM support_requests WHERE student_id = ? ORDER BY created_at DESC LIMIT 5",
        (g.user["id"],),
    )
    assessments = query_all(
        "SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC LIMIT 6",
        (g.user["id"],),
    )
    active_plans = query_all(
        "SELECT * FROM student_support_plans WHERE student_id = ? ORDER BY CASE status WHEN 'active' THEN 1 ELSE 2 END, created_at DESC LIMIT 6",
        (g.user["id"],),
    )
    settings = ensure_school_settings(g.user["school_id"])
    consent_ok = student_consent_ok(g.user["id"], settings)
    snapshot = build_student_snapshot(journals, checkins, assessments, active_plans)
    latest_assessment = assessments[0] if assessments else None
    role_board = build_student_command_center(snapshot, latest_assessment, active_plans, consent_ok, settings)
    return render_template(
        "dashboard/student.html",
        role_board=role_board,
        journals=journals,
        checkins=checkins,
        requests=requests,
        assessments=assessments,
        latest_assessment=latest_assessment,
        active_plans=active_plans,
        snapshot=snapshot,
        settings=settings,
        consent_ok=consent_ok,
    )


@bp.route("/student/checkin", methods=("POST",))
@role_required("student")
@require_csrf
def student_checkin():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        flash("Your school requires guardian consent before using student support tools.", "error")
        return redirect(url_for("dashboard.student_home"))
    mood = clamp_int(request.form.get("mood"), 1, 5, 3)
    stress = clamp_int(request.form.get("stress"), 1, 5, 3)
    energy = clamp_int(request.form.get("energy"), 1, 5, 3)
    note = clean_text(request.form.get("note"), 500)
    signal = analyze_student_signal(note, mood=mood, stress=stress, energy=energy)
    execute(
        "INSERT INTO checkins (school_id, student_id, mood, stress, energy, note, risk_level, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], g.user["id"], mood, stress, energy, note, signal["level"], utcnow()),
    )
    if signal["level"] in {"watch", "support", "urgent"}:
        create_risk_event(g.user["id"], "checkin", signal["level"], "Student check-in signal", signal["summary"])
    flash("Check-in saved. Your support team sees signals, not private diagnoses.", "success")
    return redirect(url_for("dashboard.student_home"))


@bp.route("/student/assessment", methods=("POST",))
@role_required("student")
@require_csrf
def student_assessment():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        flash("Your school requires guardian consent before using student support tools.", "error")
        return redirect(url_for("dashboard.student_home"))
    values = {
        "mood": request.form.get("mood"),
        "stress": request.form.get("stress"),
        "sleep": request.form.get("sleep"),
        "belonging": request.form.get("belonging"),
        "study_pressure": request.form.get("study_pressure"),
        "focus": request.form.get("focus"),
        "safety": request.form.get("safety"),
        "support_access": request.form.get("support_access"),
    }
    assessment = analyze_wellbeing_assessment(values)
    execute(
        """
        INSERT INTO wellbeing_assessments
        (school_id, student_id, mood, stress, sleep, belonging, study_pressure, focus, safety, support_access, score, risk_level, primary_need, recommendation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user["school_id"],
            g.user["id"],
            assessment["mood"],
            assessment["stress"],
            assessment["sleep"],
            assessment["belonging"],
            assessment["study_pressure"],
            assessment["focus"],
            assessment["safety"],
            assessment["support_access"],
            assessment["score"],
            assessment["level"],
            assessment["primary_need"],
            assessment["recommendation"],
            utcnow(),
        ),
    )
    plan = support_plan_from_assessment(assessment)
    execute(
        """
        INSERT INTO student_support_plans
        (school_id, student_id, focus_area, goal, next_step, cadence, status, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user["school_id"],
            g.user["id"],
            plan["focus_area"],
            plan["goal"],
            plan["next_step"],
            plan["cadence"],
            "active",
            None,
            utcnow(),
            utcnow(),
        ),
    )
    if assessment["level"] in {"watch", "support", "urgent"}:
        create_risk_event(g.user["id"], "wellbeing_assessment", assessment["level"], "Wellbeing scan focus", assessment["recommendation"])
    flash(f"Wellbeing scan saved. Focus area: {assessment['primary_need_label']}.", "success")
    return redirect(url_for("dashboard.student_home"))


@bp.route("/student/journal", methods=("POST",))
@role_required("student")
@require_csrf
def student_journal():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        flash("Your school requires guardian consent before using student support tools.", "error")
        return redirect(url_for("dashboard.student_home"))
    body = clean_text(request.form.get("body"), 2500)
    if len(body) < 8:
        flash("Write at least a short complete note.", "error")
        return redirect(url_for("dashboard.student_home"))
    signal = analyze_student_signal(body)
    execute(
        "INSERT INTO journal_entries (school_id, student_id, body, sentiment_score, risk_level, ai_summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], g.user["id"], body, signal["score"], signal["level"], signal["summary"], utcnow()),
    )
    if signal["level"] in {"watch", "support", "urgent"}:
        create_risk_event(g.user["id"], "journal", signal["level"], "Journal support signal", signal["summary"])
    flash("Journal saved. Private content is restricted to the support workflow.", "success")
    return redirect(url_for("dashboard.student_home"))


@bp.route("/student/support", methods=("POST",))
@role_required("student")
@require_csrf
def student_support():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        flash("Your school requires guardian consent before using student support tools.", "error")
        return redirect(url_for("dashboard.student_home"))
    topic = clean_text(request.form.get("topic"), 120) or "Support request"
    message = clean_text(request.form.get("message"), 1000)
    if len(message) < 8:
        flash("A useful request needs a little more detail.", "error")
        return redirect(url_for("dashboard.student_home"))
    execute(
        "INSERT INTO support_requests (school_id, student_id, topic, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (g.user["school_id"], g.user["id"], topic, message, utcnow()),
    )
    create_risk_event(g.user["id"], "support", "support", "Student requested help", topic)
    flash("Support request sent to the counselor workspace.", "success")
    return redirect(url_for("dashboard.student_home"))


@bp.route("/student/companion", methods=("POST",))
@role_required("student")
@require_csrf
def student_companion():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        flash("Your school requires guardian consent before using student support tools.", "error")
        return redirect(url_for("dashboard.student_home"))
    limits = feature_limits(g.user["school_plan"])
    if ai_daily_count(g.user["id"]) >= limits["ai_daily"]:
        flash("Nour reached the daily limit for your current plan.", "error")
        return redirect(url_for("dashboard.student_home"))
    message = clean_text(request.form.get("message"), 1200)
    if len(message) < 8:
        flash("Write a little more so the companion can suggest a useful next step.", "error")
        return redirect(url_for("dashboard.student_home"))
    signal = analyze_student_signal(message)
    reply = companion_reply(message, signal)
    execute(
        "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], g.user["id"], "student", message, signal["level"], "local", utcnow()),
    )
    execute(
        "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], g.user["id"], "nour", reply, signal["level"], "local", utcnow()),
    )
    if signal["level"] in {"support", "urgent"}:
        create_risk_event(g.user["id"], "companion", signal["level"], "Companion support signal", signal["summary"])
        flash(reply, "success")
    else:
        flash(reply, "success")
    return redirect(url_for("dashboard.student_home"))


@bp.route("/journal", methods=("GET", "POST"))
@role_required("student")
@require_csrf
def journal_studio():
    settings = ensure_school_settings(g.user["school_id"])
    consent_ok = student_consent_ok(g.user["id"], settings)
    if request.method == "POST":
        if not consent_ok:
            flash("Your school requires guardian consent before using journals.", "error")
            return redirect(url_for("dashboard.journal_studio"))
        body = clean_text(request.form.get("body"), 3000)
        mood = clamp_int(request.form.get("mood"), 1, 5, 3)
        if len(body) < 8:
            flash("Write at least a short complete note.", "error")
            return redirect(url_for("dashboard.journal_studio"))
        signal = analyze_student_signal(body, mood=mood)
        execute(
            "INSERT INTO journal_entries (school_id, student_id, body, sentiment_score, risk_level, ai_summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], body, signal["score"], signal["level"], signal["summary"], utcnow()),
        )
        if signal["level"] in {"watch", "support", "urgent"}:
            create_risk_event(g.user["id"], "journal", signal["level"], "Journal support signal", signal["summary"])
        flash("Journal entry saved and reflected safely.", "success")
        return redirect(url_for("dashboard.journal_studio"))
    journals = query_all("SELECT * FROM journal_entries WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["id"],))
    return render_template("dashboard/journal.html", journals=journals, consent_ok=consent_ok)


@bp.route("/companion", methods=("GET", "POST"))
@role_required("student")
@require_csrf
def companion_studio():
    settings = ensure_school_settings(g.user["school_id"])
    consent_ok = student_consent_ok(g.user["id"], settings)
    if request.method == "POST":
        if not consent_ok:
            flash("Your school requires guardian consent before using Nour.", "error")
            return redirect(url_for("dashboard.companion_studio"))
        limits = feature_limits(g.user["school_plan"])
        if ai_daily_count(g.user["id"]) >= limits["ai_daily"]:
            flash("Nour reached the daily limit for your current plan.", "error")
            return redirect(url_for("dashboard.companion_studio"))
        message = clean_text(request.form.get("message"), 1500)
        if len(message) < 4:
            flash("Write a little more so Nour can respond usefully.", "error")
            return redirect(url_for("dashboard.companion_studio"))
        signal = analyze_student_signal(message)
        reply = companion_reply(message, signal)
        execute(
            "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], "student", message, signal["level"], "local", utcnow()),
        )
        execute(
            "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], "nour", reply, signal["level"], "local", utcnow()),
        )
        if signal["level"] in {"support", "urgent"}:
            create_risk_event(g.user["id"], "nour", signal["level"], "Nour companion signal", signal["summary"])
        flash("Nour responded and saved the support context.", "success")
        return redirect(url_for("dashboard.companion_studio"))
    messages = query_all("SELECT * FROM student_ai_messages WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["id"],))
    limits = feature_limits(g.user["school_plan"])
    remaining = max(0, limits["ai_daily"] - ai_daily_count(g.user["id"]))
    return render_template("dashboard/companion.html", messages=list(reversed(messages)), consent_ok=consent_ok, remaining=remaining, daily_limit=limits["ai_daily"])


@bp.route("/api/nour/messages", methods=("POST",))
@role_required("student")
@rate_limit("nour_messages", max_requests=45, window_seconds=300)
@require_csrf
def nour_messages_api():
    settings = ensure_school_settings(g.user["school_id"])
    if not student_consent_ok(g.user["id"], settings):
        return jsonify({"ok": False, "error": "Guardian consent is required before using Nour."}), 403
    limits = feature_limits(g.user["school_plan"])
    if ai_daily_count(g.user["id"]) >= limits["ai_daily"]:
        return jsonify({"ok": False, "error": "Nour reached the daily limit for your current plan."}), 429
    payload = request.get_json(silent=True) or request.form
    message = clean_text(payload.get("message"), 1500)
    if len(message) < 4:
        return jsonify({"ok": False, "error": "Write a little more so Nour can respond usefully."}), 400
    signal = analyze_student_signal(message)
    reply = companion_reply(message, signal)
    created_at = utcnow()
    with transaction() as db:
        student_row = db.execute(
            "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], "student", message, signal["level"], "local", created_at),
        )
        nour_row = db.execute(
            "INSERT INTO student_ai_messages (school_id, student_id, role, message, risk_level, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], "nour", reply, signal["level"], "local", created_at),
        )
        if signal["level"] in {"support", "urgent"}:
            db.execute(
                "INSERT INTO risk_events (school_id, student_id, source, risk_level, title, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (g.user["school_id"], g.user["id"], "nour", signal["level"], "Nour companion signal", signal["summary"], created_at),
            )
    remaining = max(0, limits["ai_daily"] - ai_daily_count(g.user["id"]))
    return jsonify(
        {
            "ok": True,
            "saved": True,
            "remaining": remaining,
            "risk_level": signal["level"],
            "user_message": {
                "id": student_row.lastrowid,
                "role": "student",
                "message": message,
                "risk_level": signal["level"],
                "created_at": created_at,
            },
            "nour_message": {
                "id": nour_row.lastrowid,
                "role": "nour",
                "message": reply,
                "risk_level": signal["level"],
                "created_at": created_at,
            },
        }
    )


@bp.route("/goals", methods=("GET", "POST"))
@role_required("student")
@require_csrf
def student_goals():
    limits = feature_limits(g.user["school_plan"])
    if request.method == "POST":
        action = request.form.get("action", "create")
        goal_id = int(request.form.get("goal_id", 0) or 0)
        if action == "create":
            active_count = query_one("SELECT COUNT(*) AS c FROM student_goals WHERE student_id = ? AND status = 'active'", (g.user["id"],))["c"]
            if active_count >= limits["active_goals"]:
                flash("Your current plan reached its active goal limit.", "error")
                return redirect(url_for("dashboard.student_goals"))
            title = clean_text(request.form.get("title"), 160)
            description = clean_text(request.form.get("description"), 600)
            category = clean_text(request.form.get("category"), 40) or "wellbeing"
            target_date = clean_text(request.form.get("target_date"), 20) or None
            if len(title) < 3:
                flash("Goal title is required.", "error")
                return redirect(url_for("dashboard.student_goals"))
            execute(
                "INSERT INTO student_goals (school_id, student_id, title, description, category, target_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (g.user["school_id"], g.user["id"], title, description, category, target_date, utcnow(), utcnow()),
            )
            flash("Goal created.", "success")
        elif action in {"progress", "complete", "delete"}:
            goal = query_one("SELECT * FROM student_goals WHERE id = ? AND student_id = ?", (goal_id, g.user["id"]))
            if not goal:
                abort(404)
            if action == "progress":
                progress = clamp_int(request.form.get("progress"), 0, 100, goal["progress"])
                status = "completed" if progress >= 100 else "active"
                execute("UPDATE student_goals SET progress = ?, status = ?, updated_at = ? WHERE id = ?", (progress, status, utcnow(), goal_id))
            elif action == "complete":
                execute("UPDATE student_goals SET progress = 100, status = 'completed', updated_at = ? WHERE id = ?", (utcnow(), goal_id))
            else:
                execute("UPDATE student_goals SET status = 'archived', updated_at = ? WHERE id = ?", (utcnow(), goal_id))
            flash("Goal updated.", "success")
        return redirect(url_for("dashboard.student_goals"))
    goals = query_all("SELECT * FROM student_goals WHERE student_id = ? ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, created_at DESC", (g.user["id"],))
    return render_template("dashboard/goals.html", goals=goals, limits=limits)


@bp.route("/games", methods=("GET", "POST"))
@role_required("student")
@require_csrf
def games():
    full_catalog = game_catalog()
    selected_category = clean_text(request.args.get("category"), 40)
    categories = sorted({game["category"] for game in full_catalog})
    catalog = [game for game in full_catalog if not selected_category or game["category"] == selected_category]
    if request.method == "POST":
        game_name = clean_text(request.form.get("game_name"), 60)
        game_lookup = {game["id"]: game for game in full_catalog}
        if game_name not in game_lookup:
            abort(400)
        game = game_lookup[game_name]
        score = clamp_int(request.form.get("score"), 0, 100, game["points"])
        duration = clamp_int(request.form.get("duration_seconds"), 10, 3600, game["minutes"] * 60)
        execute(
            "INSERT INTO game_scores (school_id, student_id, game_name, score, duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], game_name, score, duration, utcnow()),
        )
        flash("Game result saved.", "success")
        return redirect(url_for("dashboard.games"))
    scores = query_all("SELECT * FROM game_scores WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["id"],))
    completed = {score["game_name"] for score in scores}
    return render_template("dashboard/games.html", catalog=catalog, scores=scores, categories=categories, selected_category=selected_category, completed=completed)


@bp.route("/progress")
@role_required("student")
def progress_hub():
    goals = query_all(
        "SELECT * FROM student_goals WHERE student_id = ? ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, updated_at DESC LIMIT 12",
        (g.user["id"],),
    )
    game_totals = query_one(
        "SELECT COUNT(*) AS count, COALESCE(AVG(score), 0) AS avg_score, COALESCE(SUM(duration_seconds), 0) AS seconds FROM game_scores WHERE student_id = ?",
        (g.user["id"],),
    )
    breathing_totals = query_one(
        "SELECT COUNT(*) AS count, COALESCE(SUM(duration_seconds), 0) AS seconds, COALESCE(AVG(mood_after - mood_before), 0) AS mood_delta FROM breathing_sessions WHERE student_id = ?",
        (g.user["id"],),
    )
    latest_assessment = query_one(
        "SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC LIMIT 1",
        (g.user["id"],),
    )
    recent_scores = query_all("SELECT * FROM game_scores WHERE student_id = ? ORDER BY created_at DESC LIMIT 8", (g.user["id"],))
    return render_template(
        "dashboard/progress.html",
        goals=goals,
        game_totals=game_totals,
        breathing_totals=breathing_totals,
        latest_assessment=latest_assessment,
        recent_scores=recent_scores,
    )


@bp.route("/weekly-summary")
@role_required("student")
def weekly_summary():
    cutoff = (datetime.now(UTC) - timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    checkins = query_all("SELECT * FROM checkins WHERE student_id = ? AND created_at >= ? ORDER BY created_at DESC", (g.user["id"], cutoff))
    assessments = query_all("SELECT * FROM wellbeing_assessments WHERE student_id = ? AND created_at >= ? ORDER BY created_at DESC", (g.user["id"], cutoff))
    games_rows = query_all("SELECT * FROM game_scores WHERE student_id = ? AND created_at >= ? ORDER BY created_at DESC", (g.user["id"], cutoff))
    breathing = query_all("SELECT * FROM breathing_sessions WHERE student_id = ? AND created_at >= ? ORDER BY created_at DESC", (g.user["id"], cutoff))
    support = query_all("SELECT * FROM support_requests WHERE student_id = ? AND created_at >= ? ORDER BY created_at DESC", (g.user["id"], cutoff))
    summary = {
        "checkins": len(checkins),
        "assessments": len(assessments),
        "games": len(games_rows),
        "breathing_minutes": round(sum(row["duration_seconds"] or 0 for row in breathing) / 60, 1),
        "avg_mood": round(sum(row["mood"] for row in checkins) / len(checkins), 1) if checkins else None,
        "avg_stress": round(sum(row["stress"] for row in checkins) / len(checkins), 1) if checkins else None,
    }
    return render_template(
        "dashboard/weekly_summary.html",
        cutoff=cutoff,
        summary=summary,
        checkins=checkins,
        assessments=assessments,
        games=games_rows,
        breathing=breathing,
        support=support,
    )


@bp.route("/support-plans")
@role_required("student")
def support_plans():
    plans = query_all(
        "SELECT * FROM student_support_plans WHERE student_id = ? ORDER BY CASE status WHEN 'active' THEN 1 ELSE 2 END, updated_at DESC LIMIT 40",
        (g.user["id"],),
    )
    requests = query_all("SELECT * FROM support_requests WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["id"],))
    return render_template("dashboard/support_plans.html", plans=plans, requests=requests)


@bp.route("/breathing-center", methods=("GET", "POST"))
@role_required("student")
@require_csrf
def breathing_center():
    if request.method == "POST":
        technique = clean_text(request.form.get("technique"), 40) or "box"
        cycles = clamp_int(request.form.get("cycles"), 1, 30, 4)
        duration = clamp_int(request.form.get("duration_seconds"), 30, 3600, cycles * 45)
        mood_before = clamp_int(request.form.get("mood_before"), 1, 5, 3)
        mood_after = clamp_int(request.form.get("mood_after"), 1, 5, 4)
        execute(
            "INSERT INTO breathing_sessions (school_id, student_id, technique, cycles, duration_seconds, mood_before, mood_after, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], technique, cycles, duration, mood_before, mood_after, utcnow()),
        )
        flash("Breathing session saved.", "success")
        return redirect(url_for("dashboard.breathing_center"))
    sessions = query_all("SELECT * FROM breathing_sessions WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["id"],))
    totals = query_one("SELECT COUNT(*) AS count, COALESCE(SUM(duration_seconds), 0) AS duration FROM breathing_sessions WHERE student_id = ?", (g.user["id"],))
    return render_template("dashboard/breathing.html", sessions=sessions, totals=totals)


@bp.route("/resources")
@role_required("student")
def resources():
    resources = resource_catalog()
    selected_type = clean_text(request.args.get("type"), 60)
    types = sorted({item["type"] for item in resources})
    filtered = [item for item in resources if not selected_type or item["type"] == selected_type]
    return render_template("dashboard/resources.html", resources=filtered, types=types, selected_type=selected_type)


@bp.route("/mood-diary")
@role_required("student")
def mood_diary():
    checkins = query_all("SELECT * FROM checkins WHERE student_id = ? ORDER BY created_at DESC LIMIT 30", (g.user["id"],))
    assessments = query_all("SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC LIMIT 12", (g.user["id"],))
    return render_template("dashboard/mood_diary.html", checkins=checkins, assessments=assessments)


@bp.route("/daily-tips")
@role_required("student")
def daily_tips():
    latest = query_one("SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC LIMIT 1", (g.user["id"],))
    tips = daily_tip_catalog(latest["primary_need"] if latest else "support")
    return render_template("dashboard/daily_tips.html", tips=tips, latest=latest)


@bp.route("/teacher")
@role_required("teacher")
def teacher_home():
    group = g.user["group_name"]
    rows = query_all(
        """
        SELECT users.group_name, COUNT(DISTINCT users.id) AS students,
               AVG(CASE checkins.risk_level WHEN 'steady' THEN 4 WHEN 'watch' THEN 3 WHEN 'support' THEN 2 ELSE 1 END) AS pulse
        FROM users
        LEFT JOIN checkins ON checkins.student_id = users.id
        WHERE users.school_id = ? AND users.role = 'student' AND (? IS NULL OR users.group_name = ?)
        GROUP BY users.group_name
        ORDER BY users.group_name
        """,
        (g.user["school_id"], group, group),
    )
    requests_count = query_one(
        """
        SELECT COUNT(*) AS total
        FROM support_requests
        JOIN users ON users.id = support_requests.student_id
        WHERE support_requests.school_id = ? AND (? IS NULL OR users.group_name = ?)
        """,
        (g.user["school_id"], group, group),
    )
    assessment_rows = query_all(
        """
        SELECT users.group_name,
               COUNT(DISTINCT users.id) AS students,
               ROUND(AVG(latest.score), 1) AS avg_score,
               ROUND(AVG(latest.stress), 1) AS avg_stress,
               ROUND(AVG(latest.sleep), 1) AS avg_sleep,
               ROUND(AVG(latest.belonging), 1) AS avg_belonging,
               ROUND(AVG(latest.study_pressure), 1) AS avg_study_pressure
        FROM users
        LEFT JOIN wellbeing_assessments AS latest
          ON latest.student_id = users.id
         AND latest.created_at = (
             SELECT MAX(created_at)
             FROM wellbeing_assessments AS inner_assessment
             WHERE inner_assessment.student_id = users.id
         )
        WHERE users.school_id = ? AND users.role = 'student' AND (? IS NULL OR users.group_name = ?)
        GROUP BY users.group_name
        ORDER BY users.group_name
        """,
        (g.user["school_id"], group, group),
    )
    practice_rows = query_all(
        """
        SELECT users.group_name,
               COUNT(DISTINCT CASE WHEN student_goals.status = 'active' THEN student_goals.id END) AS active_goals,
               COUNT(DISTINCT game_scores.id) AS game_sessions,
               COUNT(DISTINCT breathing_sessions.id) AS breathing_sessions
        FROM users
        LEFT JOIN student_goals ON student_goals.student_id = users.id
        LEFT JOIN game_scores ON game_scores.student_id = users.id
        LEFT JOIN breathing_sessions ON breathing_sessions.student_id = users.id
        WHERE users.school_id = ? AND users.role = 'student' AND (? IS NULL OR users.group_name = ?)
        GROUP BY users.group_name
        ORDER BY users.group_name
        """,
        (g.user["school_id"], group, group),
    )
    class_moves = class_intervention_suggestions(assessment_rows)
    role_board = build_teacher_command_center(assessment_rows, practice_rows, requests_count["total"], group)
    return render_template(
        "dashboard/teacher.html",
        role_board=role_board,
        rows=rows,
        assessment_rows=assessment_rows,
        practice_rows=practice_rows,
        class_moves=class_moves,
        requests_count=requests_count["total"],
    )


@bp.route("/counselor")
@role_required("counselor", "admin")
def counselor_home():
    settings = ensure_school_settings(g.user["school_id"])
    alerts = query_all(
        """
        SELECT risk_events.*, users.name AS student_name, users.group_name,
               assignee.name AS assigned_name,
               CAST((julianday('now') - julianday(replace(replace(risk_events.created_at, 'T', ' '), 'Z', ''))) * 24 * 60 AS INTEGER) AS age_minutes
        FROM risk_events
        JOIN users ON users.id = risk_events.student_id
        LEFT JOIN users AS assignee ON assignee.id = risk_events.assigned_to
        WHERE risk_events.school_id = ? AND risk_events.status = 'open'
        ORDER BY CASE risk_events.risk_level WHEN 'urgent' THEN 1 WHEN 'support' THEN 2 WHEN 'watch' THEN 3 ELSE 4 END, risk_events.created_at DESC
        LIMIT 30
        """,
        (g.user["school_id"],),
    )
    students = query_all(
        """
        SELECT users.id, users.name, users.email, users.group_name,
               MAX(checkins.created_at) AS last_checkin,
               MAX(journal_entries.created_at) AS last_journal,
               SUM(CASE WHEN risk_events.status = 'open' THEN 1 ELSE 0 END) AS open_events
        FROM users
        LEFT JOIN checkins ON checkins.student_id = users.id
        LEFT JOIN journal_entries ON journal_entries.student_id = users.id
        LEFT JOIN risk_events ON risk_events.student_id = users.id
        WHERE users.school_id = ? AND users.role = 'student'
        GROUP BY users.id
        ORDER BY open_events DESC, users.name
        """,
        (g.user["school_id"],),
    )
    requests = query_all(
        """
        SELECT support_requests.*, users.name AS student_name
        FROM support_requests
        JOIN users ON users.id = support_requests.student_id
        WHERE support_requests.school_id = ?
        ORDER BY support_requests.created_at DESC
        LIMIT 15
        """,
        (g.user["school_id"],),
    )
    playbooks = query_all(
        "SELECT * FROM playbooks WHERE school_id IS NULL OR school_id = ? ORDER BY is_default DESC, trigger_level, title",
        (g.user["school_id"],),
    )
    focus_rows = query_all(
        """
        SELECT users.id, users.name, users.group_name,
               latest.score, latest.risk_level, latest.primary_need, latest.recommendation, latest.created_at
        FROM users
        LEFT JOIN wellbeing_assessments AS latest
          ON latest.student_id = users.id
         AND latest.created_at = (
             SELECT MAX(created_at)
             FROM wellbeing_assessments AS inner_assessment
             WHERE inner_assessment.student_id = users.id
         )
        WHERE users.school_id = ? AND users.role = 'student'
        ORDER BY CASE latest.risk_level WHEN 'urgent' THEN 1 WHEN 'support' THEN 2 WHEN 'watch' THEN 3 WHEN 'steady' THEN 4 ELSE 5 END,
                 latest.score ASC,
                 users.name
        LIMIT 12
        """,
        (g.user["school_id"],),
    )
    overdue_count = sum(1 for alert in alerts if (alert["age_minutes"] or 0) >= settings["escalation_window_minutes"])
    role_board = build_counselor_command_center(alerts, requests, focus_rows, overdue_count, settings, g.user["id"])
    return render_template(
        "dashboard/counselor.html",
        role_board=role_board,
        alerts=alerts,
        students=students,
        requests=requests,
        playbooks=playbooks,
        focus_rows=focus_rows,
        settings=settings,
        overdue_count=overdue_count,
    )


@bp.route("/counselor/playbooks", methods=("GET", "POST"))
@role_required("counselor", "admin")
@require_csrf
def counselor_playbooks():
    if request.method == "POST":
        title = clean_text(request.form.get("title"), 120)
        trigger_level = request.form.get("trigger_level", "watch")
        action_steps = clean_text(request.form.get("action_steps"), 2000)
        if trigger_level not in {"watch", "support", "urgent"}:
            trigger_level = "watch"
        if len(title) < 3 or len(action_steps) < 15:
            flash("Playbook title and clear action steps are required.", "error")
            return redirect(url_for("dashboard.counselor_playbooks"))
        execute(
            "INSERT INTO playbooks (school_id, title, trigger_level, action_steps, is_default, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], title, trigger_level, action_steps, 0, utcnow()),
        )
        log_event("playbook_created", title, school_id=g.user["school_id"], user_id=g.user["id"])
        flash("Playbook saved.", "success")
        return redirect(url_for("dashboard.counselor_playbooks"))
    playbooks = query_all(
        "SELECT * FROM playbooks WHERE school_id IS NULL OR school_id = ? ORDER BY is_default DESC, trigger_level, title",
        (g.user["school_id"],),
    )
    settings = ensure_school_settings(g.user["school_id"])
    return render_template("dashboard/playbooks.html", playbooks=playbooks, settings=settings)


@bp.route("/reports")
@role_required("counselor", "admin")
def reports():
    risk_rows = query_all(
        "SELECT risk_level, COUNT(*) AS total FROM risk_events WHERE school_id = ? GROUP BY risk_level ORDER BY total DESC",
        (g.user["school_id"],),
    )
    group_rows = query_all(
        """
        SELECT users.group_name, COUNT(DISTINCT users.id) AS students,
               COUNT(DISTINCT risk_events.id) AS signals,
               COUNT(DISTINCT support_requests.id) AS requests
        FROM users
        LEFT JOIN risk_events ON risk_events.student_id = users.id
        LEFT JOIN support_requests ON support_requests.student_id = users.id
        WHERE users.school_id = ? AND users.role = 'student'
        GROUP BY users.group_name
        ORDER BY signals DESC, users.group_name
        """,
        (g.user["school_id"],),
    )
    assessment_rows = query_all(
        """
        SELECT primary_need,
               COUNT(*) AS total,
               ROUND(AVG(score), 1) AS avg_score,
               SUM(CASE WHEN risk_level IN ('support', 'urgent') THEN 1 ELSE 0 END) AS needs_review
        FROM wellbeing_assessments
        WHERE school_id = ?
        GROUP BY primary_need
        ORDER BY needs_review DESC, total DESC
        """,
        (g.user["school_id"],),
    )
    assessment_summary = query_one(
        """
        SELECT COUNT(*) AS total,
               ROUND(AVG(score), 1) AS avg_score,
               SUM(CASE WHEN risk_level IN ('support', 'urgent') THEN 1 ELSE 0 END) AS needs_review
        FROM wellbeing_assessments
        WHERE school_id = ?
        """,
        (g.user["school_id"],),
    )
    practice_rows = query_all(
        """
        SELECT users.group_name,
               COUNT(DISTINCT CASE WHEN student_goals.status = 'active' THEN student_goals.id END) AS active_goals,
               COUNT(DISTINCT CASE WHEN student_goals.status = 'completed' THEN student_goals.id END) AS completed_goals,
               COUNT(DISTINCT game_scores.id) AS game_sessions,
               COUNT(DISTINCT breathing_sessions.id) AS breathing_sessions
        FROM users
        LEFT JOIN student_goals ON student_goals.student_id = users.id
        LEFT JOIN game_scores ON game_scores.student_id = users.id
        LEFT JOIN breathing_sessions ON breathing_sessions.student_id = users.id
        WHERE users.school_id = ? AND users.role = 'student'
        GROUP BY users.group_name
        ORDER BY users.group_name
        """,
        (g.user["school_id"],),
    )
    totals = {
        "students": count_users(g.user["school_id"], "student"),
        "signals": query_one("SELECT COUNT(*) AS c FROM risk_events WHERE school_id = ?", (g.user["school_id"],))["c"],
        "open": query_one("SELECT COUNT(*) AS c FROM risk_events WHERE school_id = ? AND status = 'open'", (g.user["school_id"],))["c"],
        "interventions": query_one("SELECT COUNT(*) AS c FROM interventions WHERE school_id = ?", (g.user["school_id"],))["c"],
        "consent": query_one("SELECT COUNT(*) AS c FROM consent_records WHERE school_id = ?", (g.user["school_id"],))["c"],
        "goals": query_one("SELECT COUNT(*) AS c FROM student_goals WHERE school_id = ? AND status != 'archived'", (g.user["school_id"],))["c"],
        "game_sessions": query_one("SELECT COUNT(*) AS c FROM game_scores WHERE school_id = ?", (g.user["school_id"],))["c"],
        "breathing_sessions": query_one("SELECT COUNT(*) AS c FROM breathing_sessions WHERE school_id = ?", (g.user["school_id"],))["c"],
        "ai_messages": query_one("SELECT COUNT(*) AS c FROM student_ai_messages WHERE school_id = ?", (g.user["school_id"],))["c"],
        "assessments": assessment_summary["total"] or 0,
        "avg_score": assessment_summary["avg_score"] or 0,
        "assessment_needs_review": assessment_summary["needs_review"] or 0,
    }
    return render_template("dashboard/reports.html", risk_rows=risk_rows, group_rows=group_rows, assessment_rows=assessment_rows, practice_rows=practice_rows, totals=totals)


@bp.route("/counselor/student/<int:user_id>")
@role_required("counselor", "admin")
def counselor_student(user_id):
    student = same_school_user(user_id)
    if not student or student["role"] != "student":
        abort(404)
    journals = query_all("SELECT * FROM journal_entries WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,))
    checkins = query_all("SELECT * FROM checkins WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,))
    assessments = query_all("SELECT * FROM wellbeing_assessments WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,))
    plans = query_all(
        """
        SELECT student_support_plans.*, creator.name AS creator_name
        FROM student_support_plans
        LEFT JOIN users AS creator ON creator.id = student_support_plans.created_by
        WHERE student_support_plans.student_id = ? AND student_support_plans.school_id = ?
        ORDER BY CASE student_support_plans.status WHEN 'active' THEN 1 ELSE 2 END, student_support_plans.created_at DESC
        """,
        (user_id, g.user["school_id"]),
    )
    events = query_all(
        """
        SELECT risk_events.*, assignee.name AS assigned_name
        FROM risk_events
        LEFT JOIN users AS assignee ON assignee.id = risk_events.assigned_to
        WHERE risk_events.student_id = ? AND risk_events.school_id = ?
        ORDER BY risk_events.created_at DESC LIMIT 20
        """,
        (user_id, g.user["school_id"]),
    )
    interventions = query_all("SELECT interventions.*, users.name AS counselor_name FROM interventions JOIN users ON users.id = interventions.counselor_id WHERE interventions.student_id = ? ORDER BY interventions.created_at DESC", (user_id,))
    case_actions = query_all(
        """
        SELECT case_actions.*, users.name AS counselor_name, risk_events.title AS event_title
        FROM case_actions
        JOIN users ON users.id = case_actions.counselor_id
        JOIN risk_events ON risk_events.id = case_actions.risk_event_id
        WHERE case_actions.student_id = ? AND case_actions.school_id = ?
        ORDER BY case_actions.created_at DESC LIMIT 40
        """,
        (user_id, g.user["school_id"]),
    )
    consent = query_all("SELECT consent_records.*, users.name AS recorded_by_name FROM consent_records JOIN users ON users.id = consent_records.recorded_by WHERE consent_records.student_id = ? ORDER BY consent_records.created_at DESC", (user_id,))
    goals = query_all("SELECT * FROM student_goals WHERE student_id = ? ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'completed' THEN 2 ELSE 3 END, created_at DESC", (user_id,))
    games = query_all("SELECT * FROM game_scores WHERE student_id = ? ORDER BY created_at DESC LIMIT 12", (user_id,))
    breathing = query_all("SELECT * FROM breathing_sessions WHERE student_id = ? ORDER BY created_at DESC LIMIT 12", (user_id,))
    ai_messages = query_all("SELECT * FROM student_ai_messages WHERE student_id = ? ORDER BY created_at DESC LIMIT 12", (user_id,))
    case_brief = build_case_brief(student, journals, checkins, assessments, events, plans)
    return render_template(
        "dashboard/student_detail.html",
        student=student,
        journals=journals,
        checkins=checkins,
        assessments=assessments,
        plans=plans,
        events=events,
        interventions=interventions,
        consent=consent,
        goals=goals,
        games=games,
        breathing=breathing,
        ai_messages=list(reversed(ai_messages)),
        case_actions=case_actions,
        case_brief=case_brief,
    )


@bp.route("/counselor/intervention", methods=("POST",))
@role_required("counselor", "admin")
@require_csrf
def counselor_intervention():
    student_id = int(request.form.get("student_id", 0))
    student = same_school_user(student_id)
    if not student or student["role"] != "student":
        abort(404)
    action = clean_text(request.form.get("action", "Support follow-up"), 120) or "Support follow-up"
    note = clean_text(request.form.get("note"), 1200)
    if len(note) < 5:
        flash("Intervention note is too short.", "error")
        return redirect(url_for("dashboard.counselor_student", user_id=student_id))
    execute(
        "INSERT INTO interventions (school_id, student_id, counselor_id, action, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], student_id, g.user["id"], action, note, utcnow()),
    )
    execute("UPDATE risk_events SET status = 'closed', closed_at = ? WHERE student_id = ? AND school_id = ? AND status = 'open'", (utcnow(), student_id, g.user["school_id"]))
    log_event("intervention_created", action, school_id=g.user["school_id"], user_id=g.user["id"])
    flash("Intervention saved and open signals closed for this student.", "success")
    return redirect(url_for("dashboard.counselor_student", user_id=student_id))


@bp.route("/counselor/student/<int:user_id>/plan", methods=("POST",))
@role_required("counselor", "admin")
@require_csrf
def counselor_create_plan(user_id):
    student = same_school_user(user_id)
    if not student or student["role"] != "student":
        abort(404)
    focus_area = clean_text(request.form.get("focus_area"), 120) or "Support plan"
    goal = clean_text(request.form.get("goal"), 300)
    next_step = clean_text(request.form.get("next_step"), 600)
    cadence = clean_text(request.form.get("cadence"), 120) or "Weekly review"
    if len(goal) < 8 or len(next_step) < 8:
        flash("Plan goal and next step need a little more detail.", "error")
        return redirect(url_for("dashboard.counselor_student", user_id=user_id))
    execute(
        """
        INSERT INTO student_support_plans
        (school_id, student_id, focus_area, goal, next_step, cadence, status, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (g.user["school_id"], user_id, focus_area, goal, next_step, cadence, "active", g.user["id"], utcnow(), utcnow()),
    )
    log_event("support_plan_created", f"{student['email']}: {focus_area}", school_id=g.user["school_id"], user_id=g.user["id"])
    flash("Support plan added to the student case.", "success")
    return redirect(url_for("dashboard.counselor_student", user_id=user_id))


@bp.route("/counselor/alert/<int:event_id>/action", methods=("POST",))
@role_required("counselor", "admin")
@require_csrf
def counselor_alert_action(event_id):
    event = query_one(
        """
        SELECT risk_events.*, users.name AS student_name
        FROM risk_events
        JOIN users ON users.id = risk_events.student_id
        WHERE risk_events.id = ? AND risk_events.school_id = ?
        """,
        (event_id, g.user["school_id"]),
    )
    if not event:
        abort(404)
    action = request.form.get("action", "note")
    note = clean_text(request.form.get("note"), 1200)
    if action not in {"assigned", "escalated", "closed", "note"}:
        abort(400)
    if action in {"escalated", "closed"} and len(note) < 5:
        flash("A short operational note is required for escalation or closure.", "error")
        return redirect(url_for("dashboard.counselor_student", user_id=event["student_id"]))
    if action == "assigned":
        execute("UPDATE risk_events SET assigned_to = ? WHERE id = ? AND school_id = ?", (g.user["id"], event_id, g.user["school_id"]))
        note = note or "Assigned to current reviewer."
        flash("Alert assigned to you.", "success")
    elif action == "closed":
        execute("UPDATE risk_events SET status = 'closed', assigned_to = ?, closed_at = ? WHERE id = ? AND school_id = ?", (g.user["id"], utcnow(), event_id, g.user["school_id"]))
        flash("Alert closed with a case action note.", "success")
    elif action == "escalated":
        execute("UPDATE risk_events SET risk_level = 'urgent', assigned_to = ? WHERE id = ? AND school_id = ?", (g.user["id"], event_id, g.user["school_id"]))
        support_email = current_app.config.get("SUPPORT_EMAIL")
        if support_email:
            queue_email(
                g.user["school_id"],
                support_email,
                "SchoolMind urgent escalation",
                (
                    f"Workspace: {g.user['school_name']}\n"
                    f"Student: {event['student_name']}\n"
                    f"Alert: {event['title']}\n"
                    f"Reviewer: {g.user['name']}\n"
                    f"Note: {note}\n\n"
                    "Follow the school's approved human escalation protocol."
                ),
            )
        flash("Alert escalated and queued for support notification.", "success")
    else:
        flash("Case note saved.", "success")
    execute(
        "INSERT INTO case_actions (school_id, risk_event_id, student_id, counselor_id, action, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], event_id, event["student_id"], g.user["id"], action, note, utcnow()),
    )
    log_event(f"case_{action}", f"Alert {event_id}: {event['student_name']}", school_id=g.user["school_id"], user_id=g.user["id"])
    return redirect(url_for("dashboard.counselor_student", user_id=event["student_id"]))


@bp.route("/admin/onboarding", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def onboarding():
    settings = ensure_school_settings(g.user["school_id"])
    school = query_one("SELECT * FROM schools WHERE id = ?", (g.user["school_id"],))
    if request.method == "POST":
        action = request.form.get("action", "launch_profile")
        if action == "launch_profile":
            launch_language = normalize_language(request.form.get("launch_language"))
            launch_mode = request.form.get("launch_mode", "self_serve_trial")
            if launch_mode not in {"instant_demo", "self_serve_trial", "guided_pilot", "district_rollout"}:
                launch_mode = "self_serve_trial"
            country = clean_text(request.form.get("country"), 80) or school["country"]
            approval_owner = clean_text(request.form.get("approval_owner"), 120)
            data_owner = clean_text(request.form.get("data_owner"), 120)
            support_email = normalize_email(request.form.get("support_email"))
            expected_students = clamp_int(request.form.get("expected_students"), 0, 100000, 0)
            expected_staff = clamp_int(request.form.get("expected_staff"), 0, 10000, 0)
            pilot_goal = clean_text(request.form.get("pilot_goal"), 800)
            if support_email and not valid_email(support_email):
                flash("Support inbox must be a valid email address or left blank.", "error")
                return redirect(url_for("dashboard.onboarding"))
            execute("UPDATE schools SET country = ? WHERE id = ?", (country, g.user["school_id"]))
            execute(
                """
                UPDATE school_settings
                SET launch_language = ?, launch_mode = ?, approval_owner = ?, data_owner = ?, support_email = ?,
                    expected_students = ?, expected_staff = ?, pilot_goal = ?, updated_at = ?
                WHERE school_id = ?
                """,
                (
                    launch_language,
                    launch_mode,
                    approval_owner,
                    data_owner,
                    support_email,
                    expected_students,
                    expected_staff,
                    pilot_goal,
                    utcnow(),
                    g.user["school_id"],
                ),
            )
            log_event("onboarding_profile_updated", f"Launch mode {launch_mode}, expected students {expected_students}", school_id=g.user["school_id"], user_id=g.user["id"])
            flash("Launch profile saved.", "success")
            return redirect(url_for("dashboard.onboarding"))
        if action in {"mark_ready", "reset_launch"}:
            subscription = query_one("SELECT * FROM subscriptions WHERE school_id = ? ORDER BY created_at DESC LIMIT 1", (g.user["school_id"],))
            counts = role_counts()
            consent_count = query_one("SELECT COUNT(*) AS c FROM consent_records WHERE school_id = ?", (g.user["school_id"],))["c"]
            invite_count = query_one("SELECT COUNT(*) AS c FROM invite_tokens WHERE school_id = ?", (g.user["school_id"],))["c"]
            import_count = query_one("SELECT COUNT(*) AS c FROM import_batches WHERE school_id = ?", (g.user["school_id"],))["c"]
            state = build_onboarding_state(settings, counts, subscription, consent_count, invite_count, import_count)
            if action == "mark_ready":
                if not state["can_mark_ready"]:
                    flash("Workspace cannot be marked launch-ready while checklist blockers remain.", "error")
                else:
                    execute(
                        "UPDATE school_settings SET launch_stage = ?, onboarding_completed_at = ?, updated_at = ? WHERE school_id = ?",
                        ("ready", utcnow(), utcnow(), g.user["school_id"]),
                    )
                    log_event("onboarding_marked_ready", "Admin marked workspace launch-ready", school_id=g.user["school_id"], user_id=g.user["id"])
                    flash("Workspace marked launch-ready. Keep using human governance before real student data goes live.", "success")
            else:
                execute(
                    "UPDATE school_settings SET launch_stage = ?, onboarding_completed_at = NULL, updated_at = ? WHERE school_id = ?",
                    ("setup", utcnow(), g.user["school_id"]),
                )
                log_event("onboarding_reset", "Admin reset launch readiness", school_id=g.user["school_id"], user_id=g.user["id"])
                flash("Launch readiness reset to setup mode.", "success")
            return redirect(url_for("dashboard.onboarding"))
        abort(400)
    settings = ensure_school_settings(g.user["school_id"])
    subscription = query_one("SELECT * FROM subscriptions WHERE school_id = ? ORDER BY created_at DESC LIMIT 1", (g.user["school_id"],))
    counts = role_counts()
    consent_count = query_one("SELECT COUNT(*) AS c FROM consent_records WHERE school_id = ?", (g.user["school_id"],))["c"]
    invite_count = query_one("SELECT COUNT(*) AS c FROM invite_tokens WHERE school_id = ?", (g.user["school_id"],))["c"]
    import_count = query_one("SELECT COUNT(*) AS c FROM import_batches WHERE school_id = ?", (g.user["school_id"],))["c"]
    onboarding_state = build_onboarding_state(settings, counts, subscription, consent_count, invite_count, import_count)
    return render_template(
        "dashboard/onboarding.html",
        onboarding=onboarding_state,
        tasks=onboarding_state["tasks"],
        completed=onboarding_state["completed"],
        done=onboarding_state["done"],
        total=onboarding_state["total"],
        settings=settings,
        school=school,
        counts=counts,
        subscription=subscription,
        consent_count=consent_count,
        invite_count=invite_count,
        import_count=import_count,
    )


@bp.route("/admin")
@role_required("admin")
def admin_home():
    counts = role_counts()
    users = query_all("SELECT * FROM users WHERE school_id = ? ORDER BY role, name", (g.user["school_id"],))
    audit = query_all("SELECT * FROM audit_events WHERE school_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["school_id"],))
    settings = ensure_school_settings(g.user["school_id"])
    subscription = query_one("SELECT * FROM subscriptions WHERE school_id = ? ORDER BY created_at DESC LIMIT 1", (g.user["school_id"],))
    consent_count = query_one("SELECT COUNT(*) AS c FROM consent_records WHERE school_id = ?", (g.user["school_id"],))["c"]
    invite_count = query_one("SELECT COUNT(*) AS c FROM invite_tokens WHERE school_id = ?", (g.user["school_id"],))["c"]
    import_count = query_one("SELECT COUNT(*) AS c FROM import_batches WHERE school_id = ?", (g.user["school_id"],))["c"]
    outbox = query_one(
        """
        SELECT
          SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
          SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS sent
        FROM outbox_messages
        WHERE school_id = ?
        """,
        (g.user["school_id"],),
    )
    onboarding_state = build_onboarding_state(settings, counts, subscription, consent_count, invite_count, import_count)
    role_board = build_admin_command_center(counts, onboarding_state, subscription, outbox, settings)
    return render_template(
        "dashboard/admin.html",
        role_board=role_board,
        counts=counts,
        users=users,
        roles=ROLES,
        audit=audit,
        plans=PLANS,
        settings=settings,
    )


@bp.route("/admin/operations")
@role_required("admin")
def admin_operations():
    settings = ensure_school_settings(g.user["school_id"])
    counts = role_counts()
    staff_count = count_staff(g.user["school_id"])
    student_limit = PLANS[g.user["school_plan"]]["student_limit"]
    staff_limit = PLANS[g.user["school_plan"]]["staff_limit"]
    outbox = query_one(
        """
        SELECT
          SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
          SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS sent
        FROM outbox_messages
        WHERE school_id = ?
        """,
        (g.user["school_id"],),
    )
    overdue = query_one(
        """
        SELECT COUNT(*) AS c
        FROM risk_events
        WHERE school_id = ? AND status = 'open'
        AND CAST((julianday('now') - julianday(replace(replace(created_at, 'T', ' '), 'Z', ''))) * 24 * 60 AS INTEGER) >= ?
        """,
        (g.user["school_id"], settings["escalation_window_minutes"]),
    )["c"]
    config_checks = [
        {"name": "Production secret", "ok": current_app.config["SECRET_KEY"] != "dev-only-change-me", "detail": "SECRET_KEY is not the development fallback."},
        {"name": "Checkout URLs", "ok": all(checkout_url_for(plan) for plan in PLANS), "detail": "All paid plans have HTTPS checkout URLs."},
        {"name": "Billing webhook", "ok": bool(current_app.config.get("BILLING_WEBHOOK_SECRET")), "detail": "Provider webhook secret is configured."},
        {"name": "Email delivery", "ok": current_app.config.get("EMAIL_DELIVERY_MODE") in {"console", "smtp"}, "detail": f"Mode: {current_app.config.get('EMAIL_DELIVERY_MODE')}"},
        {"name": "Support owner", "ok": bool(settings["support_owner"]), "detail": settings["support_owner"] or "Missing support owner."},
        {"name": "Escalation SLA", "ok": overdue == 0, "detail": f"{overdue} open alerts are beyond the configured window."},
        {"name": "Wellbeing workflow", "ok": counts["assessments"] > 0 and counts["active_plans"] > 0, "detail": f"{counts['assessments']} scans and {counts['active_plans']} active plans recorded."},
        {"name": "Student engagement loop", "ok": counts["active_goals"] > 0 and counts["game_sessions"] > 0 and counts["breathing_sessions"] > 0 and counts["ai_messages"] > 0, "detail": f"{counts['active_goals']} goals, {counts['game_sessions']} games, {counts['breathing_sessions']} breathing sessions, {counts['ai_messages']} Nour messages."},
    ]
    usage = {
        "students": counts["students"],
        "student_limit": student_limit,
        "staff": staff_count,
        "staff_limit": staff_limit,
        "student_percent": min(100, round((counts["students"] / student_limit) * 100)) if student_limit else 0,
        "staff_percent": min(100, round((staff_count / staff_limit) * 100)) if staff_limit else 0,
    }
    return render_template("dashboard/operations.html", settings=settings, counts=counts, usage=usage, outbox=outbox, overdue=overdue, config_checks=config_checks)


@bp.route("/admin/plan-limits")
@role_required("admin")
def admin_plan_limits():
    limits = feature_limits(g.user["school_plan"])
    plan_config = PLANS.get(g.user["school_plan"], PLANS["starter"])
    counts = role_counts()
    staff_count = counts["teachers"] + counts["counselors"] + counts["admins"]
    usage = [
        {"label": "Students", "used": counts["students"], "limit": plan_config["student_limit"]},
        {"label": "Staff", "used": staff_count, "limit": plan_config["staff_limit"]},
        {"label": "Active goals", "used": counts["active_goals"], "limit": limits["active_goals"]},
        {"label": "Daily AI messages", "used": counts["ai_messages"], "limit": limits["ai_daily"]},
    ]
    checkout = {plan: checkout_url_for(plan) for plan in PLANS}
    return render_template("dashboard/plan_limits.html", limits=limits, usage=usage, plans=PLANS, checkout=checkout)


@bp.route("/admin/backups")
@role_required("admin")
def admin_backups():
    school = query_one("SELECT * FROM schools WHERE id = ?", (g.user["school_id"],))
    settings = ensure_school_settings(g.user["school_id"])
    table_names = [
        "users",
        "journal_entries",
        "checkins",
        "wellbeing_assessments",
        "student_support_plans",
        "student_goals",
        "game_scores",
        "breathing_sessions",
        "student_ai_messages",
        "risk_events",
        "support_requests",
        "interventions",
        "case_actions",
        "consent_records",
        "coupon_redemptions",
        "payment_intents",
        "subscriptions",
        "agreement_acceptances",
        "billing_events",
        "audit_events",
    ]
    counts = []
    for table in table_names:
        counts.append({"table": table, "total": query_one(f"SELECT COUNT(*) AS c FROM {table} WHERE school_id = ?", (g.user["school_id"],))["c"]})
    counts.append(
        {
            "table": "user_preferences",
            "total": query_one(
                """
                SELECT COUNT(*) AS c
                FROM user_preferences
                JOIN users ON users.id = user_preferences.user_id
                WHERE users.school_id = ?
                """,
                (g.user["school_id"],),
            )["c"],
        }
    )
    latest_export = query_one(
        "SELECT * FROM audit_events WHERE school_id = ? AND action = 'workspace_backup_downloaded' ORDER BY created_at DESC LIMIT 1",
        (g.user["school_id"],),
    )
    return render_template("dashboard/backups.html", school=school, settings=settings, counts=counts, latest_export=latest_export)


@bp.route("/admin/database")
@role_required("admin")
def admin_database():
    report = database_runtime_report()
    counts = database_table_counts(g.user["school_id"])
    release_findings = release_safety_checks(current_app.root_path.rsplit("/", 1)[0])
    return render_template("dashboard/database.html", report=report, counts=counts, release_findings=release_findings)


@bp.route("/admin/users", methods=("POST",))
@role_required("admin")
@require_csrf
def admin_create_user():
    name = clean_text(request.form.get("name"), 120)
    email = normalize_email(request.form.get("email"))
    role = request.form.get("role", "student")
    group_name = clean_text(request.form.get("group_name"), 120) or None
    password = request.form.get("password", "change-me-123")
    if role not in ROLES:
        abort(400)
    if len(name) < 2 or not valid_email(email) or len(password) < 8:
        flash("Name, valid email, and 8+ character password are required.", "error")
        return redirect(url_for("dashboard.admin_home"))
    if query_one("SELECT id FROM users WHERE email = ?", (email,)):
        flash("Email already exists.", "error")
        return redirect(url_for("dashboard.admin_home"))
    current_count = count_users(g.user["school_id"], "student") if role == "student" else count_staff(g.user["school_id"])
    if not can_add_role(g.user["school_plan"], role, current_count):
        flash("Your current plan limit blocks this user. Upgrade before adding more seats.", "error")
        return redirect(url_for("dashboard.admin_home"))
    execute(
        "INSERT INTO users (school_id, name, email, password_hash, role, group_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], name, email, generate_password_hash(password), role, group_name, utcnow()),
    )
    log_event("user_created", f"Created {role}: {email}", school_id=g.user["school_id"], user_id=g.user["id"])
    flash("User created.", "success")
    return redirect(url_for("dashboard.admin_home"))




@bp.route("/admin/users/<int:user_id>/toggle", methods=("POST",))
@role_required("admin")
@require_csrf
def admin_toggle_user(user_id):
    target = same_school_user(user_id)
    if not target:
        abort(404)
    if target["id"] == g.user["id"]:
        flash("You cannot deactivate your own admin account.", "error")
        return redirect(url_for("dashboard.admin_home"))
    new_state = 0 if target["is_active"] else 1
    execute("UPDATE users SET is_active = ? WHERE id = ? AND school_id = ?", (new_state, user_id, g.user["school_id"]))
    action = "user_deactivated" if new_state == 0 else "user_reactivated"
    log_event(action, f"{target['email']}", school_id=g.user["school_id"], user_id=g.user["id"])
    flash("User status updated.", "success")
    return redirect(url_for("dashboard.admin_home"))

@bp.route("/admin/invites", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def admin_invites():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        role = request.form.get("role", "student")
        group_name = clean_text(request.form.get("group_name"), 120) or None
        if role not in ROLES or not valid_email(email):
            flash("Valid email and role are required.", "error")
            return redirect(url_for("dashboard.admin_invites"))
        if query_one("SELECT id FROM users WHERE email = ?", (email,)):
            flash("A user already exists for that email.", "error")
            return redirect(url_for("dashboard.admin_invites"))
        current_count = count_users(g.user["school_id"], "student") if role == "student" else count_staff(g.user["school_id"])
        if not can_add_role(g.user["school_plan"], role, current_count):
            flash("Your current plan limit blocks this invite. Upgrade before adding more seats.", "error")
            return redirect(url_for("dashboard.admin_invites"))
        token, token_hash = new_token()
        expires_at = (datetime.now(UTC) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        execute(
            "INSERT INTO invite_tokens (school_id, email, role, group_name, token_hash, created_by, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], email, role, group_name, token_hash, g.user["id"], expires_at, utcnow()),
        )
        invite_path = url_for("auth.accept_invite", token=token)
        invite_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + invite_path
        queue_template_email(
            g.user["school_id"],
            email,
            "workspace_invite",
            {"school_name": g.user["school_name"], "invite_url": invite_url},
            message_type="workspace_invite",
            metadata="admin_invite",
        )
        log_event("invite_created", f"Invite queued for {email}", school_id=g.user["school_id"], user_id=g.user["id"])
        flash("Invite created and queued in the outbox.", "success")
        return redirect(url_for("dashboard.admin_invites"))
    invites = query_all("SELECT * FROM invite_tokens WHERE school_id = ? ORDER BY created_at DESC LIMIT 30", (g.user["school_id"],))
    outbox = query_all("SELECT * FROM outbox_messages WHERE school_id = ? ORDER BY created_at DESC LIMIT 30", (g.user["school_id"],))
    return render_template("dashboard/invites.html", invites=invites, outbox=outbox, roles=ROLES)


@bp.route("/admin/outbox", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def admin_outbox():
    if request.method == "POST":
        action = request.form.get("action", "dispatch")
        if action == "test_email":
            recipient = normalize_email(request.form.get("recipient") or current_app.config.get("TEST_EMAIL_RECIPIENT") or g.user["email"])
            if not valid_email(recipient):
                flash("A valid test recipient email is required.", "error")
            else:
                queue_test_email(g.user["school_id"], recipient)
                log_event("outbox_test_email_queued", f"Test email queued for {recipient}", school_id=g.user["school_id"], user_id=g.user["id"])
                flash("Test email queued. Use dispatch only after console or SMTP delivery is configured.", "success")
            return redirect(url_for("dashboard.admin_outbox"))
        result = dispatch_queued(limit=25)
        log_event("outbox_dispatch", f"Sent {result['sent']}, failed {result['failed']}, skipped {result.get('skipped', 0)}", school_id=g.user["school_id"], user_id=g.user["id"])
        if result["sent"]:
            flash(f"Outbox dispatch finished: {result['sent']} sent, {result['failed']} failed.", "success")
        else:
            flash(f"No message sent. Failed: {result['failed']}. Check email delivery health before relying on this in production.", "error")
        return redirect(url_for("dashboard.admin_outbox"))
    outbox = latest_outbox_messages(g.user["school_id"], limit=100)
    counts = query_all("SELECT status, COUNT(*) AS total FROM outbox_messages WHERE school_id = ? GROUP BY status", (g.user["school_id"],))
    health = email_delivery_health(g.user["school_id"])
    return render_template("dashboard/outbox.html", outbox=outbox, counts=counts, health=health)


@bp.route("/admin/import", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def admin_import():
    if request.method == "POST":
        raw = clean_text(request.form.get("csv_rows"), 20000)
        imported, skipped, notes = import_users_from_csv(raw)
        execute(
            "INSERT INTO import_batches (school_id, created_by, imported_count, skipped_count, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], g.user["id"], imported, skipped, "; ".join(notes)[:500], utcnow()),
        )
        log_event("users_imported", f"Imported {imported}, skipped {skipped}", school_id=g.user["school_id"], user_id=g.user["id"])
        flash(f"Import finished: {imported} created, {skipped} skipped.", "success" if imported else "error")
        return redirect(url_for("dashboard.admin_import"))
    batches = query_all("SELECT * FROM import_batches WHERE school_id = ? ORDER BY created_at DESC LIMIT 10", (g.user["school_id"],))
    return render_template("dashboard/import.html", batches=batches)


@bp.route("/admin/settings", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def admin_settings():
    settings = ensure_school_settings(g.user["school_id"])
    school = query_one("SELECT * FROM schools WHERE id = ?", (g.user["school_id"],))
    if request.method == "POST":
        support_owner = clean_text(request.form.get("support_owner"), 120)
        country = clean_text(request.form.get("country"), 80) or school["country"]
        escalation_window = clamp_int(request.form.get("escalation_window_minutes"), 5, 1440, 60)
        data_retention_days = clamp_int(request.form.get("data_retention_days"), 30, 3650, 365)
        guardian_required = 1 if request.form.get("guardian_consent_required") == "on" else 0
        emergency_instructions = clean_text(request.form.get("emergency_instructions"), 1200)
        execute("UPDATE schools SET country = ? WHERE id = ?", (country, g.user["school_id"]))
        execute(
            """
            UPDATE school_settings
            SET support_owner = ?, escalation_window_minutes = ?, emergency_instructions = ?, data_retention_days = ?, guardian_consent_required = ?, updated_at = ?
            WHERE school_id = ?
            """,
            (support_owner, escalation_window, emergency_instructions, data_retention_days, guardian_required, utcnow(), g.user["school_id"]),
        )
        log_event("settings_updated", "School settings updated", school_id=g.user["school_id"], user_id=g.user["id"])
        flash("Settings saved.", "success")
        return redirect(url_for("dashboard.admin_settings"))
    return render_template("dashboard/settings.html", settings=settings, school=school)


@bp.route("/admin/consent", methods=("GET", "POST"))
@role_required("admin")
@require_csrf
def admin_consent():
    if request.method == "POST":
        student_id = int(request.form.get("student_id", 0))
        student = same_school_user(student_id)
        if not student or student["role"] != "student":
            abort(404)
        guardian_name = clean_text(request.form.get("guardian_name"), 120)
        guardian_email = normalize_email(request.form.get("guardian_email"))
        status = request.form.get("status", "pending")
        note = clean_text(request.form.get("note"), 600)
        if status not in {"pending", "recorded", "declined"}:
            status = "pending"
        if len(guardian_name) < 2 or not valid_email(guardian_email):
            flash("Guardian name and valid email are required.", "error")
            return redirect(url_for("dashboard.admin_consent"))
        execute(
            "INSERT INTO consent_records (school_id, student_id, guardian_name, guardian_email, status, note, recorded_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], student_id, guardian_name, guardian_email, status, note, g.user["id"], utcnow()),
        )
        log_event("consent_recorded", f"Consent {status} for student {student_id}", school_id=g.user["school_id"], user_id=g.user["id"])
        flash("Consent record saved.", "success")
        return redirect(url_for("dashboard.admin_consent"))
    students = query_all("SELECT * FROM users WHERE school_id = ? AND role = 'student' ORDER BY name", (g.user["school_id"],))
    records = query_all(
        """
        SELECT consent_records.*, users.name AS student_name
        FROM consent_records
        JOIN users ON users.id = consent_records.student_id
        WHERE consent_records.school_id = ?
        ORDER BY consent_records.created_at DESC
        LIMIT 40
        """,
        (g.user["school_id"],),
    )
    return render_template("dashboard/consent.html", students=students, records=records)


@bp.route("/admin/billing")
@role_required("admin")
def admin_billing():
    subscription = query_one("SELECT * FROM subscriptions WHERE school_id = ? ORDER BY created_at DESC LIMIT 1", (g.user["school_id"],))
    checkout = {
        plan: {"monthly": checkout_url_for(plan, "monthly"), "annual": checkout_url_for(plan, "annual")}
        for plan in PLANS
    }
    events = query_all("SELECT * FROM billing_events WHERE school_id = ? ORDER BY created_at DESC LIMIT 20", (g.user["school_id"],))
    coupons = query_all("SELECT code, description, discount_percent, applies_to_plan, status, expires_at FROM coupon_codes WHERE status = 'active' ORDER BY discount_percent DESC LIMIT 10")
    return render_template("dashboard/billing.html", subscription=subscription, plans=PLANS, pricing_catalog=pricing_catalog(), checkout=checkout, events=events, coupons=coupons, allow_manual_billing=current_app.config.get("ALLOW_SCHOOL_ADMIN_MANUAL_BILLING", False))


@bp.route("/admin/billing/checkout/<plan>")
@role_required("admin")
@rate_limit("billing_checkout", max_requests=60, window_seconds=300)
def billing_checkout(plan):
    if plan not in PLANS:
        abort(404)
    billing_cycle = normalize_billing_cycle(request.args.get("billing_cycle"))
    checkout = checkout_url_for(plan, billing_cycle)
    amount = plan_price(plan) if billing_cycle == "monthly" else PLANS[plan].get("annual_price", 0)
    execute(
        "INSERT INTO billing_events (school_id, event_type, plan, amount, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], "checkout_requested", plan, amount, f"Admin opened {billing_cycle} checkout flow", utcnow()),
    )
    if not checkout:
        flash(f"{billing_cycle.title()} checkout URL is missing. Add it in environment variables before selling automated subscriptions.", "error")
        return redirect(url_for("dashboard.admin_billing"))
    return redirect(checkout)


@bp.route("/admin/billing/manual-activate", methods=("POST",))
@role_required("admin")
@rate_limit("billing_manual_activate", max_requests=30, window_seconds=300)
@require_csrf
def billing_manual_activate():
    if not current_app.config.get("ALLOW_SCHOOL_ADMIN_MANUAL_BILLING", False):
        flash("Manual billing activation is disabled for school admins. Use provider checkout or platform-owner activation for paid subscriptions.", "error")
        return redirect(url_for("dashboard.admin_billing"))
    plan = request.form.get("plan", "starter")
    if plan not in PLANS:
        abort(400)
    reference = clean_text(request.form.get("reference"), 120) or "manual"
    coupon_code = clean_text(request.form.get("coupon_code"), 40).upper()
    ok, message = activate_subscription_with_coupon(g.user["school_id"], plan, coupon_code, reference)
    if not ok:
        flash(message, "error")
        return redirect(url_for("dashboard.admin_billing"))
    preview = preview_coupon(coupon_code, plan)
    execute(
        """
        INSERT INTO payment_intents (school_id, plan, amount, discount_amount, final_amount, coupon_code, status, provider_reference, created_at, paid_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.user["school_id"],
            plan,
            preview["base_amount"],
            preview["discount_amount"],
            preview["final_amount"],
            coupon_code,
            "paid",
            reference,
            utcnow(),
            utcnow(),
        ),
    )
    execute(
        "INSERT INTO billing_events (school_id, event_type, plan, amount, provider_reference, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], "manual_activation", plan, preview["final_amount"], reference, f"Manual activation recorded by admin. Coupon: {coupon_code or 'none'}", utcnow()),
    )
    log_event("billing_manual_activation", f"Plan {plan} activated manually", school_id=g.user["school_id"], user_id=g.user["id"])
    flash("Manual billing activation recorded.", "success")
    return redirect(url_for("dashboard.admin_billing"))


@bp.route("/admin/data-retention/run", methods=("POST",))
@role_required("admin")
@require_csrf
def admin_run_retention():
    settings = ensure_school_settings(g.user["school_id"])
    days = clamp_int(settings["data_retention_days"], 30, 3650, 365)
    cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    deletions = []
    targets = [
        ("journal_entries", "created_at < ?"),
        ("checkins", "created_at < ?"),
        ("wellbeing_assessments", "created_at < ?"),
        ("student_support_plans", "created_at < ? AND status != 'active'"),
        ("student_goals", "created_at < ? AND status != 'active'"),
        ("game_scores", "created_at < ?"),
        ("breathing_sessions", "created_at < ?"),
        ("student_ai_messages", "created_at < ?"),
        ("support_requests", "created_at < ? AND status != 'new'"),
        ("risk_events", "created_at < ? AND status = 'closed'"),
        ("interventions", "created_at < ?"),
        ("payment_intents", "created_at < ? AND status != 'pending'"),
        ("audit_events", "created_at < ?"),
    ]
    for table, condition in targets:
        before = query_one(f"SELECT COUNT(*) AS c FROM {table} WHERE school_id = ? AND {condition}", (g.user["school_id"], cutoff))["c"]
        execute(f"DELETE FROM {table} WHERE school_id = ? AND {condition}", (g.user["school_id"], cutoff))
        deletions.append(f"{table}:{before}")
    log_event("retention_cleanup", ", ".join(deletions), school_id=g.user["school_id"], user_id=g.user["id"])
    flash("Data retention cleanup completed: " + ", ".join(deletions), "success")
    return redirect(url_for("dashboard.admin_settings"))


@bp.route("/admin/security")
@role_required("admin")
def admin_security():
    users = query_all(
        """
        SELECT id, name, email, role, is_active, failed_login_count, locked_until, last_login_at, password_changed_at
        FROM users
        WHERE school_id = ?
        ORDER BY CASE WHEN locked_until IS NULL THEN 1 ELSE 0 END, role, name
        """,
        (g.user["school_id"],),
    )
    events = query_all(
        """
        SELECT account_security_events.*, users.name AS user_name
        FROM account_security_events
        LEFT JOIN users ON users.id = account_security_events.user_id
        WHERE account_security_events.school_id = ?
        ORDER BY account_security_events.created_at DESC
        LIMIT 80
        """,
        (g.user["school_id"],),
    )
    one_day_ago = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary = {
        "locked": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND locked_until IS NOT NULL", (g.user["school_id"],))["c"],
        "failed_today": query_one("SELECT COUNT(*) AS c FROM account_security_events WHERE school_id = ? AND success = 0 AND created_at >= ?", (g.user["school_id"], one_day_ago))["c"],
        "reset_pending": query_one("SELECT COUNT(*) AS c FROM password_reset_tokens WHERE school_id = ? AND status = 'pending'", (g.user["school_id"],))["c"],
    }
    return render_template("dashboard/security.html", users=users, events=events, summary=summary)


@bp.route("/admin/security/users/<int:user_id>/unlock", methods=("POST",))
@role_required("admin")
@require_csrf
def admin_unlock_user(user_id):
    target = same_school_user(user_id)
    if not target:
        abort(404)
    execute("UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ? AND school_id = ?", (user_id, g.user["school_id"]))
    execute(
        "INSERT INTO account_security_events (school_id, user_id, email, event_type, success, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], user_id, target["email"], "admin_unlock", 1, f"Unlocked by {g.user['email']}", utcnow()),
    )
    log_event("user_unlocked", target["email"], school_id=g.user["school_id"], user_id=g.user["id"])
    flash("User account unlocked.", "success")
    return redirect(url_for("dashboard.admin_security"))


@bp.route("/admin/security/users/<int:user_id>/reset-link", methods=("POST",))
@role_required("admin")
@require_csrf
def admin_queue_reset_link(user_id):
    target = same_school_user(user_id)
    if not target or not target["is_active"]:
        abort(404)
    token, token_hash = new_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    execute(
        "INSERT INTO password_reset_tokens (school_id, user_id, email, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], user_id, target["email"], token_hash, expires_at, utcnow()),
    )
    reset_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + url_for("auth.reset_password", token=token)
    queue_email(g.user["school_id"], target["email"], "SchoolMind admin password reset", f"Your school admin queued a password reset. Use this link within 2 hours: {reset_url}")
    execute(
        "INSERT INTO account_security_events (school_id, user_id, email, event_type, success, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], user_id, target["email"], "admin_reset_queued", 1, f"Queued by {g.user['email']}", utcnow()),
    )
    log_event("admin_password_reset_queued", target["email"], school_id=g.user["school_id"], user_id=g.user["id"])
    flash("Password reset link queued in the outbox.", "success")
    return redirect(url_for("dashboard.admin_security"))


def import_users_from_csv(raw):
    imported = 0
    skipped = 0
    notes = []
    reader = csv.DictReader(io.StringIO(raw))
    required = {"name", "email", "role"}
    if not reader.fieldnames or not required.issubset({field.strip() for field in reader.fieldnames}):
        return 0, 1, ["Missing header: name,email,role"]
    for row in reader:
        name = clean_text(row.get("name"), 120)
        email = normalize_email(row.get("email"))
        role = clean_text(row.get("role"), 20).lower()
        group_name = clean_text(row.get("group_name"), 120) or None
        password = row.get("password") or "change-me-123"
        if role not in ROLES or len(name) < 2 or not valid_email(email) or len(password) < 8:
            skipped += 1
            continue
        if query_one("SELECT id FROM users WHERE email = ?", (email,)):
            skipped += 1
            continue
        current_count = count_users(g.user["school_id"], "student") if role == "student" else count_staff(g.user["school_id"])
        if not can_add_role(g.user["school_plan"], role, current_count):
            skipped += 1
            notes.append("Plan limit reached")
            continue
        execute(
            "INSERT INTO users (school_id, name, email, password_hash, role, group_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["school_id"], name, email, generate_password_hash(password), role, group_name, utcnow()),
        )
        imported += 1
    return imported, skipped, notes


def student_consent_ok(student_id, settings):
    if not settings["guardian_consent_required"]:
        return True
    row = query_one(
        "SELECT id FROM consent_records WHERE school_id = ? AND student_id = ? AND status = 'recorded' ORDER BY created_at DESC LIMIT 1",
        (g.user["school_id"], student_id),
    )
    return row is not None


def role_counts():
    return {
        "students": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = 'student'", (g.user["school_id"],))["c"],
        "teachers": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = 'teacher'", (g.user["school_id"],))["c"],
        "counselors": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = 'counselor'", (g.user["school_id"],))["c"],
        "admins": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = 'admin'", (g.user["school_id"],))["c"],
        "open_events": query_one("SELECT COUNT(*) AS c FROM risk_events WHERE school_id = ? AND status = 'open'", (g.user["school_id"],))["c"],
        "assessments": query_one("SELECT COUNT(*) AS c FROM wellbeing_assessments WHERE school_id = ?", (g.user["school_id"],))["c"],
        "active_plans": query_one("SELECT COUNT(*) AS c FROM student_support_plans WHERE school_id = ? AND status = 'active'", (g.user["school_id"],))["c"],
        "active_goals": query_one("SELECT COUNT(*) AS c FROM student_goals WHERE school_id = ? AND status = 'active'", (g.user["school_id"],))["c"],
        "game_sessions": query_one("SELECT COUNT(*) AS c FROM game_scores WHERE school_id = ?", (g.user["school_id"],))["c"],
        "breathing_sessions": query_one("SELECT COUNT(*) AS c FROM breathing_sessions WHERE school_id = ?", (g.user["school_id"],))["c"],
        "ai_messages": query_one("SELECT COUNT(*) AS c FROM student_ai_messages WHERE school_id = ?", (g.user["school_id"],))["c"],
    }


def count_staff(school_id):
    return query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role != 'student'", (school_id,))["c"]


def clamp_int(value, low, high, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def checkbox_int(name):
    return 1 if request.form.get(name) == "on" else 0


def create_risk_event(student_id, source, level, title, detail):
    execute(
        "INSERT INTO risk_events (school_id, student_id, source, risk_level, title, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (g.user["school_id"], student_id, source, level, title, detail, utcnow()),
    )


def ai_daily_count(student_id):
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    return query_one(
        "SELECT COUNT(*) AS c FROM student_ai_messages WHERE student_id = ? AND role = 'student' AND created_at >= ?",
        (student_id, start),
    )["c"]


def game_catalog():
    games = [
        {"id": "calm_match", "name": "Calm Match", "category": "calm", "minutes": 2, "points": 78, "skill": "Emotion naming", "prompt": "Match a feeling to one healthy next action."},
        {"id": "focus_tiles", "name": "Focus Tiles", "category": "focus", "minutes": 3, "points": 82, "skill": "Attention reset", "prompt": "Choose the next small task before the timer ends."},
        {"id": "gratitude_builder", "name": "Gratitude Builder", "category": "reflection", "minutes": 2, "points": 80, "skill": "Positive recall", "prompt": "Name one person, one moment, and one strength from today."},
        {"id": "breathing_score", "name": "Breathing Score", "category": "calm", "minutes": 3, "points": 84, "skill": "Calm routine", "prompt": "Complete breathing cycles and record how your mood changed."},
        {"id": "mood_match", "name": "Mood Match", "category": "emotions", "minutes": 2, "points": 76, "skill": "Feeling vocabulary", "prompt": "Choose the feeling word that best fits a school situation."},
        {"id": "kindness_quest", "name": "Kindness Quest", "category": "belonging", "minutes": 4, "points": 88, "skill": "Peer connection", "prompt": "Pick one low-pressure action that makes the next hour easier for someone."},
        {"id": "stress_signals_sort", "name": "Stress Signals Sort", "category": "calm", "minutes": 3, "points": 86, "skill": "Body signal awareness", "prompt": "Sort pressure signs into body, thought, and action cues."},
        {"id": "reflection_cards", "name": "Reflection Cards", "category": "reflection", "minutes": 3, "points": 79, "skill": "Self-reflection", "prompt": "Choose a prompt and turn it into one support-ready sentence."},
        {"id": "study_break_planner", "name": "Study Break Planner", "category": "study", "minutes": 4, "points": 85, "skill": "Workload planning", "prompt": "Build a 20-minute study block with a recovery break."},
        {"id": "emotion_vocabulary", "name": "Emotion Vocabulary", "category": "emotions", "minutes": 2, "points": 74, "skill": "Precise language", "prompt": "Upgrade a vague feeling into a specific support signal."},
        {"id": "calm_puzzle", "name": "Calm Puzzle", "category": "focus", "minutes": 5, "points": 90, "skill": "Pattern focus", "prompt": "Finish a small pattern while keeping a steady pace."},
        {"id": "help_path_builder", "name": "Help Path Builder", "category": "support", "minutes": 3, "points": 87, "skill": "Asking for help", "prompt": "Choose who to ask, what to say, and when to follow up."},
    ]
    options = {
        "calm_match": ["Name the feeling, then choose one next action.", "Ignore the feeling until later.", "Try to solve every problem at once."],
        "focus_tiles": ["Pick one 20-minute task and start a timer.", "Open every assignment at once.", "Wait until the deadline feels urgent."],
        "gratitude_builder": ["Name one person, one moment, and one strength.", "Compare yourself to another student.", "Skip reflection and keep scrolling."],
        "breathing_score": ["Start four slow cycles and notice the change.", "Rush the breath to finish faster.", "Hold breath until uncomfortable."],
        "mood_match": ["Use a precise word like tense, tired, hopeful, or stuck.", "Say only fine even when it is not useful.", "Use a label that feels harsh."],
        "kindness_quest": ["Choose one low-pressure kind action today.", "Try to fix every friendship at once.", "Make a public competition out of kindness."],
        "stress_signals_sort": ["Sort signs into body, thought, and action cues.", "Treat every stress cue as failure.", "Hide all signals from support adults."],
        "reflection_cards": ["Write one support-ready sentence from the prompt.", "Write something unsafe to get attention.", "Leave the card blank."],
        "study_break_planner": ["Plan work, break, and one ask-for-help point.", "Study without any break.", "Cancel sleep to finish everything."],
        "emotion_vocabulary": ["Upgrade vague words into specific support signals.", "Use the strongest word every time.", "Avoid naming the feeling."],
        "calm_puzzle": ["Finish slowly and keep a steady pace.", "Race until frustrated.", "Quit after one small mistake."],
        "help_path_builder": ["Choose who, what to say, and when to follow up.", "Ask no one and hope it disappears.", "Send a vague message with no next step."],
    }
    for game in games:
        game["options"] = options.get(game["id"], ["Choose one safe next step.", "Skip the activity.", "Do everything at once."])
    return games


def resource_catalog():
    return [
        {"title": "Study pressure plan", "type": "School skill", "body": "Pick one deadline, one blocked task, and one person who can help before the end of the day."},
        {"title": "Conflict reset", "type": "Social skill", "body": "Write what happened, what you need, and one safe adult who can help mediate."},
        {"title": "Sleep recovery", "type": "Routine", "body": "Move one task earlier, reduce late screen time, and ask for workload support if sleep keeps dropping."},
        {"title": "When it feels unsafe", "type": "Safety", "body": "Use your school's approved human support path immediately. SchoolMind is not an emergency service."},
        {"title": "Exam week map", "type": "School skill", "body": "List every test, mark the hardest one, and build the first 20-minute review block."},
        {"title": "Asking for help script", "type": "Support", "body": "Use: I am stuck on this part, I tried this step, and I need help choosing the next step."},
        {"title": "Friendship repair note", "type": "Social skill", "body": "Separate facts, feelings, and the one repair action you can control."},
        {"title": "Grounding reset", "type": "Calm", "body": "Notice five things you see, four you feel, three you hear, two you smell, and one next action."},
    ]


def daily_tip_catalog(primary_need):
    tips = {
        "calm": ["Name the pressure in one sentence.", "Take four slow breathing cycles.", "Ask for one concrete support action."],
        "study_load": ["Choose the first assignment only.", "Set a 20-minute work block.", "Tell a teacher which deadline is hardest."],
        "sleep": ["Move one task away from bedtime.", "Prepare tomorrow's first step before sleeping.", "Flag sleep loss to a trusted adult if it repeats."],
        "belonging": ["Say hello to one safe person.", "Join one low-pressure group activity.", "Ask a teacher for a seating or pairing change if needed."],
        "support": ["Write who your support owner is.", "Save the easiest way to contact them.", "Ask early while the problem is still small."],
    }
    return tips.get(primary_need, tips["support"])
