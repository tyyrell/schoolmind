import secrets
from datetime import UTC, datetime, timedelta
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import count_users, execute, ensure_school_settings, log_event, query_one, utcnow
from .security import rate_limit, require_csrf, client_ip
from .decorators import load_logged_in_user
from .services.billing import can_add_role, plan_price, checkout_url_for, normalize_billing_cycle, seats_for_plan
from .services.mailer import queue_template_email
from .services.tokens import hash_token, new_token
from .services.validators import clean_text, normalize_email, slugify, valid_email
from .services.google_oauth import (
    GoogleOAuthError,
    authorization_url,
    complete_google_login,
    google_config,
    is_google_enabled,
)

bp = Blueprint("auth", __name__)


@bp.before_app_request
def before_request():
    load_logged_in_user()


@bp.route("/login", methods=("GET", "POST"))
@rate_limit("login", max_requests=40, window_seconds=300)
@require_csrf
def login():
    if g.user:
        return redirect(url_for("dashboard.app_home"))
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        user = query_one(
            """
            SELECT users.*, schools.name AS school_name, schools.plan AS school_plan, schools.status AS school_status
            FROM users
            JOIN schools ON schools.id = users.school_id
            WHERE users.email = ? AND users.is_active = 1
            """,
            (email,),
        )
        if user and account_is_locked(user):
            record_security_event(email, "login_locked", user["school_id"], user["id"], False, "Locked account blocked login")
            flash("This account is temporarily locked after repeated failed attempts. Ask an admin to unlock it or wait before retrying.", "error")
            return render_template("auth/login.html")
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            execute("UPDATE users SET failed_login_count = 0, locked_until = NULL, last_login_at = ? WHERE id = ?", (utcnow(), user["id"]))
            record_security_event(email, "login_success", user["school_id"], user["id"], True, "User signed in")
            log_event("login", "User signed in", school_id=user["school_id"], user_id=user["id"])
            return redirect(url_for("dashboard.app_home"))
        if user:
            next_count = int(user["failed_login_count"] or 0) + 1
            locked_until = None
            detail = f"Failed password attempt {next_count}"
            if next_count >= 5:
                locked_until = (datetime.now(UTC) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                detail = "Account locked for 15 minutes after repeated failed attempts"
            execute("UPDATE users SET failed_login_count = ?, locked_until = ? WHERE id = ?", (next_count, locked_until, user["id"]))
            record_security_event(email, "login_failed", user["school_id"], user["id"], False, detail)
        else:
            record_security_event(email, "login_failed_unknown", None, None, False, "Unknown email login attempt")
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", google_enabled=is_google_enabled(url_for("auth.google_callback", _external=True)))


@bp.route("/auth/google")
@rate_limit("google_login", max_requests=30, window_seconds=300)
def google_start():
    redirect_uri = url_for("auth.google_callback", _external=True)
    if not is_google_enabled(redirect_uri):
        flash("Google sign-in is not configured for this deployment.", "error")
        return redirect(url_for("auth.login"))
    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    session["google_oauth_started_at"] = int(datetime.now(UTC).timestamp())
    try:
        return redirect(authorization_url(state, redirect_uri))
    except GoogleOAuthError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.login"))


@bp.route("/auth/google/callback")
@rate_limit("google_callback", max_requests=40, window_seconds=300)
def google_callback():
    expected_state = session.pop("google_oauth_state", "")
    started_at = int(session.pop("google_oauth_started_at", 0) or 0)
    state = request.args.get("state", "")
    code = request.args.get("code", "")
    if not expected_state or not state or not secrets.compare_digest(expected_state, state):
        flash("Google sign-in was rejected because the session changed.", "error")
        return redirect(url_for("auth.login"))
    if int(datetime.now(UTC).timestamp()) - started_at > 600:
        flash("Google sign-in expired. Try again.", "error")
        return redirect(url_for("auth.login"))
    if not code:
        flash("Google did not return a sign-in code.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    try:
        profile = complete_google_login(code, redirect_uri)
    except GoogleOAuthError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.login"))
    user = query_one(
        """
        SELECT users.*, schools.name AS school_name, schools.plan AS school_plan, schools.status AS school_status
        FROM users
        JOIN schools ON schools.id = users.school_id
        WHERE users.google_sub = ? AND users.is_active = 1
        """,
        (profile["sub"],),
    )
    created = False
    if not user:
        user = query_one(
            """
            SELECT users.*, schools.name AS school_name, schools.plan AS school_plan, schools.status AS school_status
            FROM users
            JOIN schools ON schools.id = users.school_id
            WHERE users.email = ? AND users.is_active = 1
            """,
            (profile["email"],),
        )
        if user:
            execute(
                "UPDATE users SET google_sub = ?, auth_provider = 'google', avatar_url = ? WHERE id = ?",
                (profile["sub"], profile["avatar_url"], user["id"]),
            )
        else:
            cfg = google_config(redirect_uri)
            if not cfg["allow_auto_create"]:
                flash("No account exists for this Google email. Ask your school admin for an invite.", "error")
                return redirect(url_for("auth.login"))
            school = query_one("SELECT * FROM schools WHERE slug = ?", (cfg["default_school_slug"],))
            if not school:
                flash("Google auto-create is configured, but the default school was not found.", "error")
                return redirect(url_for("auth.login"))
            role = cfg["default_role"] if cfg["default_role"] in {"student", "teacher", "counselor", "admin"} else "student"
            user_id = execute(
                """
                INSERT INTO users (school_id, name, email, password_hash, role, google_sub, auth_provider, avatar_url, password_changed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    school["id"],
                    profile["name"],
                    profile["email"],
                    generate_password_hash(secrets.token_urlsafe(24)),
                    role,
                    profile["sub"],
                    "google",
                    profile["avatar_url"],
                    utcnow(),
                    utcnow(),
                ),
            ).lastrowid
            record_agreement_acceptance(school["id"], user_id, "google_user_terms", "2026-07")
            created = True
            user = query_one(
                """
                SELECT users.*, schools.name AS school_name, schools.plan AS school_plan, schools.status AS school_status
                FROM users
                JOIN schools ON schools.id = users.school_id
                WHERE users.id = ?
                """,
                (user_id,),
            )
    session.clear()
    session["user_id"] = user["id"]
    execute("UPDATE users SET failed_login_count = 0, locked_until = NULL, last_login_at = ? WHERE id = ?", (utcnow(), user["id"]))
    record_security_event(profile["email"], "google_login_success", user["school_id"], user["id"], True, "Google sign-in")
    log_event("google_signup" if created else "google_login", "Google sign-in completed", school_id=user["school_id"], user_id=user["id"])
    return redirect(url_for("dashboard.app_home"))




@bp.route("/forgot-password", methods=("GET", "POST"))
@rate_limit("forgot_password", max_requests=20, window_seconds=600)
@require_csrf
def forgot_password():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        user = query_one("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
        if user:
            token, token_hash = new_token()
            expires_at = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            execute(
                "INSERT INTO password_reset_tokens (school_id, user_id, email, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user["school_id"], user["id"], email, token_hash, expires_at, utcnow()),
            )
            reset_path = url_for("auth.reset_password", token=token, _external=False)
            reset_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + reset_path
            queue_template_email(
                user["school_id"],
                email,
                "password_reset",
                {"reset_url": reset_url},
                message_type="password_reset",
                metadata="forgot_password",
            )
            log_event("password_reset_requested", "Password reset queued", school_id=user["school_id"], user_id=user["id"])
        flash("If the email exists, a reset message was queued.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=("GET", "POST"))
@rate_limit("reset_password", max_requests=30, window_seconds=600)
@require_csrf
def reset_password(token):
    token_hash = hash_token(token)
    reset = query_one(
        "SELECT password_reset_tokens.*, users.name AS user_name FROM password_reset_tokens JOIN users ON users.id = password_reset_tokens.user_id WHERE token_hash = ? AND status = 'pending'",
        (token_hash,),
    )
    if not reset:
        flash("Reset link is invalid or already used.", "error")
        return redirect(url_for("auth.login"))
    expires_at = datetime.fromisoformat(reset["expires_at"].replace("Z", "+00:00"))
    if datetime.now(UTC) > expires_at:
        execute("UPDATE password_reset_tokens SET status = 'expired' WHERE id = ?", (reset["id"],))
        flash("Reset link expired.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/reset_password.html", reset=reset)
        execute("UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL, password_changed_at = ? WHERE id = ?", (generate_password_hash(password), utcnow(), reset["user_id"]))
        execute("UPDATE password_reset_tokens SET status = 'used', used_at = ? WHERE id = ?", (utcnow(), reset["id"]))
        log_event("password_reset_completed", "Password reset completed", school_id=reset["school_id"], user_id=reset["user_id"])
        flash("Password updated. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", reset=reset)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.index"))


@bp.route("/start", methods=("GET", "POST"))
@rate_limit("start", max_requests=25, window_seconds=600)
@require_csrf
def start():
    selected_plan = request.args.get("plan") or request.form.get("plan") or "starter"
    selected_billing_cycle = normalize_billing_cycle(request.args.get("billing_cycle") or request.form.get("billing_cycle"))
    if not current_app.config.get("ALLOW_SELF_REGISTER", True):
        flash("Public workspace creation is disabled for this deployment. Use admin invites or contact the platform owner.", "error")
        return redirect(url_for("public.contact"))
    allow_trials = query_one("SELECT value FROM site_settings WHERE key = ?", ("allow_public_trials",))
    if allow_trials and allow_trials["value"] == "false":
        flash("Public trial creation is currently disabled. Contact the SchoolMind team for onboarding.", "error")
        return redirect(url_for("public.contact"))
    if request.method == "POST":
        school_name = clean_text(request.form.get("school_name"), 120)
        admin_name = clean_text(request.form.get("admin_name"), 120)
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        plan = request.form.get("plan", "starter")
        country = clean_text(request.form.get("country"), 80) or "Global"
        billing_cycle = normalize_billing_cycle(request.form.get("billing_cycle"))
        if plan == "scale":
            flash("Large or custom deployments should start with a guided pilot, not a self-serve workspace.", "error")
            return redirect(url_for("public.pilot"))
        if plan not in {"starter", "growth"}:
            plan = "starter"
        if len(school_name) < 2 or len(admin_name) < 2:
            flash("School name and admin name are required.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        if not valid_email(email):
            flash("A valid email is required.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        if request.form.get("accept_terms") != "on":
            flash("You must accept the platform terms and privacy commitments before creating a workspace.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        if request.form.get("accept_trial_boundary") != "on" or request.form.get("accept_human_review") != "on":
            flash("You must confirm the trial boundary and human-review responsibilities before creating a workspace.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        if query_one("SELECT id FROM users WHERE email = ?", (email,)):
            flash("That email is already registered.", "error")
            return render_template("auth/start.html", selected_plan=plan, selected_billing_cycle=selected_billing_cycle)
        slug_base = slugify(school_name)
        slug = slug_base
        suffix = 2
        while query_one("SELECT id FROM schools WHERE slug = ?", (slug,)):
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        trial_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        school_id = execute(
            "INSERT INTO schools (name, slug, country, plan, status, trial_ends_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (school_name, slug, country, plan, "trial", trial_end, utcnow()),
        ).lastrowid
        ensure_school_settings(school_id)
        execute(
            "INSERT INTO subscriptions (school_id, plan, status, seats, monthly_price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (school_id, plan, "trialing", seats_for_plan(plan), plan_price(plan), utcnow()),
        )
        execute(
            "INSERT INTO billing_events (school_id, event_type, plan, amount, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (school_id, "trial_started", plan, 0, f"Workspace created from public trial form. Intended billing cycle: {billing_cycle}", utcnow()),
        )
        user_id = execute(
            "INSERT INTO users (school_id, name, email, password_hash, role, password_changed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (school_id, admin_name, email, generate_password_hash(password), "admin", utcnow(), utcnow()),
        ).lastrowid
        record_agreement_acceptance(school_id, user_id, "workspace_terms", "2026-07")
        queue_template_email(
            school_id,
            email,
            "trial_started",
            {
                "admin_name": admin_name,
                "school_name": school_name,
                "workspace_url": current_app.config["PUBLIC_BASE_URL"].rstrip("/") + url_for("dashboard.onboarding"),
            },
            message_type="trial",
            metadata=f"plan={plan};billing_cycle={billing_cycle}",
        )
        log_event("tenant_created", f"School started on {plan}", school_id=school_id, user_id=user_id)
        session.clear()
        session["user_id"] = user_id
        checkout_url = checkout_url_for(plan, billing_cycle)
        if checkout_url:
            flash("Your workspace is ready. Complete checkout to activate billing.", "success")
        else:
            flash("Your workspace is ready. The 30-day trial is active. Add checkout URLs before automated paid sales.", "success")
        return redirect(url_for("dashboard.onboarding"))
    return render_template("auth/start.html", selected_plan=selected_plan, selected_billing_cycle=selected_billing_cycle)


@bp.route("/invite/<token>", methods=("GET", "POST"))
@rate_limit("invite", max_requests=30, window_seconds=600)
@require_csrf
def accept_invite(token):
    token_hash = hash_token(token)
    invite = query_one(
        """
        SELECT invite_tokens.*, schools.name AS school_name, schools.plan AS school_plan
        FROM invite_tokens
        JOIN schools ON schools.id = invite_tokens.school_id
        WHERE invite_tokens.token_hash = ? AND invite_tokens.status = 'pending'
        """,
        (token_hash,),
    )
    if not invite:
        flash("Invite is invalid or already used.", "error")
        return redirect(url_for("auth.login"))
    expires_at = datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00"))
    if datetime.now(UTC) > expires_at:
        execute("UPDATE invite_tokens SET status = 'expired' WHERE id = ?", (invite["id"],))
        flash("Invite expired. Ask your school admin for a new one.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        name = clean_text(request.form.get("name"), 120)
        password = request.form.get("password", "")
        if len(name) < 2 or len(password) < 8:
            flash("Name and an 8+ character password are required.", "error")
            return render_template("auth/accept_invite.html", invite=invite)
        if request.form.get("accept_terms") != "on":
            flash("You must accept the platform terms and privacy commitments before joining.", "error")
            return render_template("auth/accept_invite.html", invite=invite)
        if query_one("SELECT id FROM users WHERE email = ?", (invite["email"],)):
            execute("UPDATE invite_tokens SET status = 'blocked' WHERE id = ?", (invite["id"],))
            flash("An account already exists for this email.", "error")
            return redirect(url_for("auth.login"))
        current_count = count_users(invite["school_id"], "student") if invite["role"] == "student" else query_one("SELECT COUNT(*) AS c FROM users WHERE school_id = ? AND role != 'student'", (invite["school_id"],))["c"]
        if not can_add_role(invite["school_plan"], invite["role"], current_count):
            flash("The school plan has no free seats for this invite.", "error")
            return redirect(url_for("auth.login"))
        user_id = execute(
            "INSERT INTO users (school_id, name, email, password_hash, role, group_name, password_changed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (invite["school_id"], name, invite["email"], generate_password_hash(password), invite["role"], invite["group_name"], utcnow(), utcnow()),
        ).lastrowid
        execute("UPDATE invite_tokens SET status = 'accepted', accepted_at = ? WHERE id = ?", (utcnow(), invite["id"]))
        record_agreement_acceptance(invite["school_id"], user_id, "user_terms", "2026-07")
        log_event("invite_accepted", f"Accepted invite for {invite['email']}", school_id=invite["school_id"], user_id=user_id)
        session.clear()
        session["user_id"] = user_id
        flash("Account created from invite.", "success")
        return redirect(url_for("dashboard.app_home"))
    return render_template("auth/accept_invite.html", invite=invite)


def record_agreement_acceptance(school_id, user_id, agreement_type, version):
    ip_address = client_ip()[:80]
    user_agent = request.headers.get("User-Agent", "")[:240]
    execute(
        "INSERT INTO agreement_acceptances (school_id, user_id, agreement_type, version, ip_address, user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (school_id, user_id, agreement_type, version, ip_address, user_agent, utcnow()),
    )



def account_is_locked(user):
    locked_until = user["locked_until"] if "locked_until" in user.keys() else None
    if not locked_until:
        return False
    try:
        locked_until_dt = datetime.fromisoformat(str(locked_until).replace("Z", "+00:00"))
    except ValueError:
        return False
    if datetime.now(UTC) >= locked_until_dt:
        execute("UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (user["id"],))
        return False
    return True


def record_security_event(email, event_type, school_id=None, user_id=None, success=False, detail=""):
    ip_address = client_ip()[:80]
    user_agent = request.headers.get("User-Agent", "")[:240]
    execute(
        """
        INSERT INTO account_security_events (school_id, user_id, email, event_type, success, ip_address, user_agent, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (school_id, user_id, normalize_email(email), event_type, 1 if success else 0, ip_address, user_agent, clean_text(detail, 500), utcnow()),
    )
