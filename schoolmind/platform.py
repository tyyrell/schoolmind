from datetime import UTC, datetime, timedelta
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ensure_platform_preferences, execute, log_event, query_all, query_one, utcnow
from .decorators import platform_required
from .i18n import FONT_SIZES, SUPPORTED_LANGUAGES, SUPPORTED_THEMES, normalize_language, normalize_theme
from .security import rate_limit, require_csrf
from .services.validators import clean_text, normalize_email
from .config import PLANS

bp = Blueprint("platform", __name__, url_prefix="/platform")


@bp.route("/login", methods=("GET", "POST"))
@rate_limit("platform_login", max_requests=30, window_seconds=300)
@require_csrf
def platform_login():
    if getattr(g, "platform_admin", None):
        return redirect(url_for("platform.platform_home"))
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        admin = query_one("SELECT * FROM platform_admins WHERE email = ? AND is_active = 1", (email,))
        if admin and platform_account_is_locked(admin):
            record_platform_security_event(email, "platform_login_locked", admin["id"], False, "Locked platform account blocked login")
            flash("This platform account is temporarily locked after repeated failed attempts.", "error")
            return render_template("platform/login.html")
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["platform_admin_id"] = admin["id"]
            execute("UPDATE platform_admins SET failed_login_count = 0, locked_until = NULL, last_login_at = ? WHERE id = ?", (utcnow(), admin["id"]))
            record_platform_security_event(email, "platform_login_success", admin["id"], True, "Platform owner signed in")
            return redirect(url_for("platform.platform_home"))
        if admin:
            next_count = int(admin["failed_login_count"] or 0) + 1
            locked_until = None
            detail = f"Failed platform password attempt {next_count}"
            if next_count >= 5:
                locked_until = (datetime.now(UTC) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                detail = "Platform account locked for 15 minutes after repeated failed attempts"
            execute("UPDATE platform_admins SET failed_login_count = ?, locked_until = ? WHERE id = ?", (next_count, locked_until, admin["id"]))
            record_platform_security_event(email, "platform_login_failed", admin["id"], False, detail)
        else:
            record_platform_security_event(email, "platform_login_failed_unknown", None, False, "Unknown platform email login attempt")
        flash("Invalid platform email or password.", "error")
    return render_template("platform/login.html")


@bp.route("/logout")
def platform_logout():
    session.clear()
    return redirect(url_for("public.index"))


@bp.route("")
@platform_required
def platform_home():
    stats = {
        "schools": query_one("SELECT COUNT(*) AS c FROM schools")["c"],
        "active": query_one("SELECT COUNT(*) AS c FROM schools WHERE status = 'active'")["c"],
        "trial": query_one("SELECT COUNT(*) AS c FROM schools WHERE status = 'trial'")["c"],
        "users": query_one("SELECT COUNT(*) AS c FROM users")["c"],
        "open_events": query_one("SELECT COUNT(*) AS c FROM risk_events WHERE status = 'open'")["c"],
        "leads": query_one("SELECT COUNT(*) AS c FROM sales_leads WHERE status = 'new'")["c"],
    }
    schools = query_all(
        """
        SELECT schools.*, COUNT(users.id) AS users_count,
               SUM(CASE WHEN users.role = 'student' THEN 1 ELSE 0 END) AS students_count,
               SUM(CASE WHEN risk_events.status = 'open' THEN 1 ELSE 0 END) AS open_events
        FROM schools
        LEFT JOIN users ON users.school_id = schools.id
        LEFT JOIN risk_events ON risk_events.school_id = schools.id
        GROUP BY schools.id
        ORDER BY schools.created_at DESC
        LIMIT 50
        """
    )
    leads = query_all("SELECT * FROM sales_leads ORDER BY created_at DESC LIMIT 20")
    billing = query_all("SELECT billing_events.*, schools.name AS school_name FROM billing_events JOIN schools ON schools.id = billing_events.school_id ORDER BY billing_events.created_at DESC LIMIT 25")
    coupons = query_all("SELECT * FROM coupon_codes ORDER BY created_at DESC LIMIT 10")
    settings = query_all("SELECT * FROM site_settings ORDER BY key")
    return render_template("platform/home.html", stats=stats, schools=schools, leads=leads, billing=billing, coupons=coupons, settings=settings)


@bp.route("/account", methods=("GET", "POST"))
@platform_required
@require_csrf
def platform_account_settings():
    preferences = ensure_platform_preferences(g.platform_admin["id"])
    if request.method == "POST":
        action = request.form.get("action", "preferences")
        if action == "profile":
            name = clean_text(request.form.get("name"), 120)
            if len(name) < 2:
                flash("A display name is required.", "error")
                return redirect(url_for("platform.platform_account_settings"))
            execute("UPDATE platform_admins SET name = ? WHERE id = ?", (name, g.platform_admin["id"]))
            flash("Profile saved.", "success")
        elif action == "preferences":
            language = normalize_language(request.form.get("language"))
            theme = normalize_theme(request.form.get("theme"))
            font_size = request.form.get("font_size") if request.form.get("font_size") in FONT_SIZES else "normal"
            execute(
                """
                UPDATE platform_admin_preferences
                SET language = ?, theme = ?, font_size = ?, reduced_motion = ?, high_contrast = ?, dyslexia_friendly = ?,
                    personalization_completed = 1, personalization_dismissed = 0, updated_at = ?
                WHERE admin_id = ?
                """,
                (
                    language,
                    theme,
                    font_size,
                    checkbox_int("reduced_motion"),
                    checkbox_int("high_contrast"),
                    checkbox_int("dyslexia_friendly"),
                    utcnow(),
                    g.platform_admin["id"],
                ),
            )
            flash("Settings saved.", "success")
        elif action == "notifications":
            execute(
                "UPDATE platform_admin_preferences SET notify_email = ?, updated_at = ? WHERE admin_id = ?",
                (checkbox_int("notify_email"), utcnow(), g.platform_admin["id"]),
            )
            flash("Notification settings saved.", "success")
        elif action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not check_password_hash(g.platform_admin["password_hash"], current_password) or len(new_password) < 8:
                flash("Current password or new password is invalid.", "error")
                return redirect(url_for("platform.platform_account_settings"))
            execute(
                "UPDATE platform_admins SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), g.platform_admin["id"]),
            )
            record_platform_security_event(g.platform_admin["email"], "platform_password_changed", g.platform_admin["id"], True, "Platform admin changed password")
            flash("Password updated.", "success")
        else:
            abort(400)
        return redirect(url_for("platform.platform_account_settings"))
    preferences = ensure_platform_preferences(g.platform_admin["id"])
    return render_template(
        "platform/account.html",
        preferences=preferences,
        languages=SUPPORTED_LANGUAGES,
        themes=SUPPORTED_THEMES,
        font_sizes=FONT_SIZES,
    )


@bp.route("/schools/<int:school_id>")
@platform_required
def platform_school(school_id):
    school = query_one("SELECT * FROM schools WHERE id = ?", (school_id,))
    if not school:
        abort(404)
    counts = {
        "students": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role = 'student'", (school_id,))["c"],
        "staff": query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role != 'student'", (school_id,))["c"],
        "open_events": query_one("SELECT COUNT(*) AS c FROM risk_events WHERE school_id = ? AND status = 'open'", (school_id,))["c"],
        "queued_email": query_one("SELECT COUNT(*) AS c FROM outbox_messages WHERE school_id = ? AND status = 'queued'", (school_id,))["c"],
    }
    users = query_all("SELECT id, name, email, role, is_active, last_login_at, locked_until FROM users WHERE school_id = ? ORDER BY role, name", (school_id,))
    settings = query_one("SELECT * FROM school_settings WHERE school_id = ?", (school_id,))
    audit = query_all("SELECT * FROM audit_events WHERE school_id = ? ORDER BY created_at DESC LIMIT 40", (school_id,))
    return render_template("platform/school.html", school=school, counts=counts, users=users, settings=settings, audit=audit)


@bp.route("/schools/<int:school_id>/status", methods=("POST",))
@platform_required
@require_csrf
def platform_school_status(school_id):
    school = query_one("SELECT * FROM schools WHERE id = ?", (school_id,))
    if not school:
        abort(404)
    status = clean_text(request.form.get("status"), 30)
    if status not in {"trial", "active", "past_due", "suspended", "cancelled"}:
        abort(400)
    execute("UPDATE schools SET status = ? WHERE id = ?", (status, school_id))
    log_event("platform_school_status", f"Platform set status to {status}", school_id=school_id, user_id=None)
    flash("School status updated.", "success")
    return redirect(url_for("platform.platform_school", school_id=school_id))


@bp.route("/coupons", methods=("GET", "POST"))
@platform_required
@require_csrf
def platform_coupons():
    if request.method == "POST":
        code = clean_text(request.form.get("code"), 40).upper().replace(" ", "")
        description = clean_text(request.form.get("description"), 240)
        discount_percent = parse_int(request.form.get("discount_percent"), 0)
        max_redemptions = parse_int(request.form.get("max_redemptions"), 100)
        applies_to_plan = clean_text(request.form.get("applies_to_plan"), 30) or "all"
        expires_at = clean_text(request.form.get("expires_at"), 30) or None
        if not code or discount_percent < 1 or discount_percent > 100 or max_redemptions < 1 or applies_to_plan not in (set(PLANS) | {"all"}):
            flash("Coupon code, valid discount, and plan scope are required.", "error")
            return redirect(url_for("platform.platform_coupons"))
        if query_one("SELECT id FROM coupon_codes WHERE code = ?", (code,)):
            flash("Coupon already exists.", "error")
            return redirect(url_for("platform.platform_coupons"))
        execute(
            """
            INSERT INTO coupon_codes (code, description, discount_percent, max_redemptions, applies_to_plan, expires_at, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, description, discount_percent, max_redemptions, applies_to_plan, expires_at, g.platform_admin["id"], utcnow()),
        )
        flash("Coupon created.", "success")
        return redirect(url_for("platform.platform_coupons"))
    coupons = query_all("SELECT * FROM coupon_codes ORDER BY created_at DESC")
    redemptions = query_all(
        """
        SELECT coupon_redemptions.*, coupon_codes.code, schools.name AS school_name
        FROM coupon_redemptions
        JOIN coupon_codes ON coupon_codes.id = coupon_redemptions.coupon_id
        JOIN schools ON schools.id = coupon_redemptions.school_id
        ORDER BY coupon_redemptions.created_at DESC LIMIT 50
        """
    )
    return render_template("platform/coupons.html", coupons=coupons, redemptions=redemptions, plans=PLANS)


@bp.route("/coupons/<int:coupon_id>/status", methods=("POST",))
@platform_required
@require_csrf
def platform_coupon_status(coupon_id):
    coupon = query_one("SELECT * FROM coupon_codes WHERE id = ?", (coupon_id,))
    if not coupon:
        abort(404)
    status = clean_text(request.form.get("status"), 30)
    if status not in {"active", "disabled"}:
        abort(400)
    execute("UPDATE coupon_codes SET status = ? WHERE id = ?", (status, coupon_id))
    flash("Coupon status updated.", "success")
    return redirect(url_for("platform.platform_coupons"))


@bp.route("/settings", methods=("GET", "POST"))
@platform_required
@require_csrf
def platform_settings():
    allowed = {"public_announcement", "hero_title", "hero_subtitle", "maintenance_mode", "allow_public_trials"}
    if request.method == "POST":
        for key in allowed:
            value = clean_text(request.form.get(key), 1200)
            if key in {"maintenance_mode", "allow_public_trials"}:
                value = "true" if value == "true" else "false"
            execute(
                """
                INSERT INTO site_settings (key, value, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, updated_at = excluded.updated_at
                """,
                (key, value, g.platform_admin["id"], utcnow()),
            )
        flash("Site settings updated.", "success")
        return redirect(url_for("platform.platform_settings"))
    rows = query_all("SELECT * FROM site_settings ORDER BY key")
    settings = {row["key"]: row["value"] for row in rows}
    return render_template("platform/settings.html", settings=settings)


def platform_account_is_locked(admin):
    locked_until = admin["locked_until"] if "locked_until" in admin.keys() else None
    if not locked_until:
        return False
    try:
        locked_until_dt = datetime.fromisoformat(str(locked_until).replace("Z", "+00:00"))
    except ValueError:
        return False
    if datetime.now(UTC) >= locked_until_dt:
        execute("UPDATE platform_admins SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (admin["id"],))
        return False
    return True


def record_platform_security_event(email, event_type, platform_admin_id=None, success=False, detail=""):
    execute(
        """
        INSERT INTO account_security_events (school_id, user_id, email, event_type, success, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (None, platform_admin_id, normalize_email(email), event_type, 1 if success else 0, clean_text(detail, 500), utcnow()),
    )


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def checkbox_int(name):
    return 1 if request.form.get(name) == "on" else 0
