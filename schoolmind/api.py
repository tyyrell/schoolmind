import csv
import io
import hmac
import json
from hashlib import sha256
from flask import Blueprint, Response, abort, current_app, g, jsonify, request
from .decorators import role_required
from .db import SCHEMA_VERSION, execute, log_event, query_all, query_one, transaction, utcnow
from .security import rate_limit
from .services.billing import checkout_url_for

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/health")
@rate_limit("health", max_requests=60, window_seconds=60)
def health():
    return {"ok": True, "service": "schoolmind-ai"}


@bp.route("/readiness")
@rate_limit("readiness", max_requests=30, window_seconds=60)
def readiness():
    db_ok = True
    try:
        query_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False
    checkout_ready = all(checkout_url_for(plan) for plan in ("starter", "growth", "scale"))
    production_key = current_app.config["SECRET_KEY"] != "dev-only-change-me"
    return jsonify({
        "ok": db_ok and production_key,
        "database": db_ok,
        "database_engine": current_app.config.get("DATABASE_ENGINE", "sqlite"),
        "schema_version": SCHEMA_VERSION,
        "production_secret": production_key,
        "checkout_ready": checkout_ready,
        "environment": current_app.config.get("APP_ENV", "development"),
    })


@bp.route("/billing/webhook", methods=("POST",))
@rate_limit("billing_webhook", max_requests=120, window_seconds=300)
def billing_webhook():
    secret = current_app.config.get("BILLING_WEBHOOK_SECRET", "")
    if not secret:
        abort(404)
    body = request.get_data() or b""
    provided = request.headers.get("X-SchoolMind-Signature", "")
    expected = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    if not hmac.compare_digest(provided, expected):
        abort(403)
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        abort(400)
    school_slug = str(payload.get("school_slug", "")).strip().lower()
    plan = str(payload.get("plan", "starter")).strip().lower()
    status = str(payload.get("status", "active")).strip().lower()
    event_type = str(payload.get("event_type", "provider_payment")).strip()[:120]
    provider_reference = str(payload.get("provider_reference", "")).strip()[:160]
    try:
        amount = int(payload.get("amount", 0) or 0)
    except (TypeError, ValueError):
        abort(400)
    if amount < 0:
        abort(400)
    if plan not in {"starter", "growth", "scale"} or status not in {"active", "past_due", "cancelled", "trialing"}:
        abort(400)
    school = query_one("SELECT * FROM schools WHERE slug = ?", (school_slug,))
    if not school:
        abort(404)
    paid_at = utcnow() if status == "active" else None
    school_status = "active" if status == "active" else status
    with transaction() as db:
        db.execute("UPDATE schools SET plan = ?, status = ? WHERE id = ?", (plan, school_status, school["id"]))
        db.execute(
            """
            INSERT INTO subscriptions (school_id, plan, status, seats, monthly_price, checkout_reference, renewed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (school["id"], plan, status, seats_for_webhook_plan(plan), price_for_webhook_plan(plan), provider_reference, paid_at, utcnow()),
        )
        db.execute(
            "INSERT INTO billing_events (school_id, event_type, plan, amount, provider_reference, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (school["id"], event_type, plan, amount, provider_reference, "Provider webhook accepted", utcnow()),
        )
        db.execute(
            """
            INSERT INTO payment_intents (school_id, plan, amount, final_amount, status, provider_reference, created_at, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (school["id"], plan, amount, amount, "paid" if status == "active" else status, provider_reference, utcnow(), paid_at),
        )
    return jsonify({"ok": True, "school_slug": school_slug, "plan": plan, "status": status})


def price_for_webhook_plan(plan):
    prices = {"starter": 49, "growth": 149, "scale": 399}
    return prices.get(plan, 49)


def seats_for_webhook_plan(plan):
    seats = {"starter": 250, "growth": 1500, "scale": 5000}
    return seats.get(plan, 250)


@bp.route("/pulse")
@role_required("counselor", "admin")
def pulse():
    rows = query_all(
        """
        SELECT risk_level, COUNT(*) AS total
        FROM risk_events
        WHERE school_id = ? AND status = 'open'
        GROUP BY risk_level
        """,
        (g.user["school_id"],),
    )
    return jsonify({row["risk_level"]: row["total"] for row in rows})


@bp.route("/export/students.csv")
@role_required("admin", "counselor")
def export_students():
    rows = query_all(
        """
        SELECT users.name, users.email, users.group_name,
               COUNT(risk_events.id) AS open_events,
               latest.score AS wellbeing_score,
               latest.risk_level AS wellbeing_level,
               latest.primary_need AS wellbeing_focus
        FROM users
        LEFT JOIN risk_events ON risk_events.student_id = users.id AND risk_events.status = 'open'
        LEFT JOIN wellbeing_assessments AS latest
          ON latest.student_id = users.id
         AND latest.created_at = (
             SELECT MAX(created_at)
             FROM wellbeing_assessments AS inner_assessment
             WHERE inner_assessment.student_id = users.id
         )
        WHERE users.school_id = ? AND users.role = 'student'
        GROUP BY users.id
        ORDER BY users.name
        """,
        (g.user["school_id"],),
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "email", "group", "open_events", "wellbeing_score", "wellbeing_level", "wellbeing_focus"])
    for row in rows:
        writer.writerow([
            safe_cell(row["name"]),
            safe_cell(row["email"]),
            safe_cell(row["group_name"] or ""),
            row["open_events"],
            row["wellbeing_score"] or "",
            safe_cell(row["wellbeing_level"] or ""),
            safe_cell(row["wellbeing_focus"] or ""),
        ])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=students.csv"})


@bp.route("/export/workspace.json")
@role_required("admin")
def export_workspace_json():
    school_id = g.user["school_id"]
    school = dict(query_one("SELECT id, name, slug, country, plan, status, trial_ends_at, created_at FROM schools WHERE id = ?", (school_id,)))
    settings = dict(query_one("SELECT * FROM school_settings WHERE school_id = ?", (school_id,)) or {})
    tables = {
        "users": "SELECT id, name, email, role, group_name, auth_provider, is_active, created_at FROM users WHERE school_id = ? ORDER BY role, name",
        "user_preferences": "SELECT user_preferences.user_id, user_preferences.language, user_preferences.theme, user_preferences.font_size, user_preferences.reduced_motion, user_preferences.high_contrast, user_preferences.dyslexia_friendly, user_preferences.notify_email, user_preferences.notify_support, user_preferences.personalization_completed, user_preferences.personalization_dismissed, user_preferences.updated_at FROM user_preferences JOIN users ON users.id = user_preferences.user_id WHERE users.school_id = ? ORDER BY users.role, users.name",
        "journal_entries": "SELECT id, student_id, sentiment_score, risk_level, ai_summary, created_at FROM journal_entries WHERE school_id = ? ORDER BY created_at DESC",
        "checkins": "SELECT id, student_id, mood, stress, energy, note, risk_level, created_at FROM checkins WHERE school_id = ? ORDER BY created_at DESC",
        "risk_events": "SELECT id, student_id, source, risk_level, title, detail, status, assigned_to, created_at, closed_at FROM risk_events WHERE school_id = ? ORDER BY created_at DESC",
        "wellbeing_assessments": "SELECT id, student_id, mood, stress, sleep, belonging, study_pressure, focus, safety, support_access, score, risk_level, primary_need, recommendation, created_at FROM wellbeing_assessments WHERE school_id = ? ORDER BY created_at DESC",
        "student_support_plans": "SELECT id, student_id, focus_area, goal, next_step, cadence, status, created_by, created_at, updated_at FROM student_support_plans WHERE school_id = ? ORDER BY created_at DESC",
        "student_goals": "SELECT id, student_id, title, description, category, target_date, progress, status, created_at, updated_at FROM student_goals WHERE school_id = ? ORDER BY created_at DESC",
        "game_scores": "SELECT id, student_id, game_name, score, duration_seconds, created_at FROM game_scores WHERE school_id = ? ORDER BY created_at DESC",
        "breathing_sessions": "SELECT id, student_id, technique, cycles, duration_seconds, mood_before, mood_after, created_at FROM breathing_sessions WHERE school_id = ? ORDER BY created_at DESC",
        "student_ai_messages": "SELECT id, student_id, role, risk_level, provider, created_at FROM student_ai_messages WHERE school_id = ? ORDER BY created_at DESC",
        "support_requests": "SELECT id, student_id, topic, message, status, created_at FROM support_requests WHERE school_id = ? ORDER BY created_at DESC",
        "interventions": "SELECT id, student_id, counselor_id, action, note, created_at FROM interventions WHERE school_id = ? ORDER BY created_at DESC",
        "case_actions": "SELECT id, risk_event_id, student_id, counselor_id, action, note, created_at FROM case_actions WHERE school_id = ? ORDER BY created_at DESC",
        "agreement_acceptances": "SELECT id, user_id, agreement_type, version, created_at FROM agreement_acceptances WHERE school_id = ? ORDER BY created_at DESC",
        "consent_records": "SELECT id, student_id, guardian_name, guardian_email, status, note, recorded_by, created_at FROM consent_records WHERE school_id = ? ORDER BY created_at DESC",
        "subscriptions": "SELECT id, plan, status, seats, monthly_price, discount_percent, coupon_code, current_period_end, renewed_at, created_at FROM subscriptions WHERE school_id = ? ORDER BY created_at DESC",
        "payment_intents": "SELECT id, plan, amount, discount_amount, final_amount, coupon_code, status, provider_reference, created_at, paid_at FROM payment_intents WHERE school_id = ? ORDER BY created_at DESC",
        "coupon_redemptions": "SELECT id, coupon_id, subscription_id, discount_amount, created_at FROM coupon_redemptions WHERE school_id = ? ORDER BY created_at DESC",
        "billing_events": "SELECT id, event_type, plan, amount, provider_reference, note, created_at FROM billing_events WHERE school_id = ? ORDER BY created_at DESC",
        "audit_events": "SELECT id, user_id, action, detail, created_at FROM audit_events WHERE school_id = ? ORDER BY created_at DESC LIMIT 500",
    }
    data = {
        "schema_version": SCHEMA_VERSION,
        "backup_type": "workspace_export",
        "exported_at": utcnow(),
        "school": school,
        "settings": settings,
        "records": {},
        "record_counts": {},
    }
    for name, sql in tables.items():
        rows = [dict(row) for row in query_all(sql, (school_id,))]
        data["records"][name] = rows
        data["record_counts"][name] = len(rows)
    log_event("workspace_backup_downloaded", "Admin downloaded workspace JSON backup", school_id=school_id, user_id=g.user["id"])
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(payload, mimetype="application/json", headers={"Content-Disposition": "attachment; filename=schoolmind-workspace-backup.json"})


def safe_cell(value):
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
