"""
SchoolMind AI v21 — Main Flask application
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mental health platform for students (Arabic + English).

Architecture:
  app.py        — routes & request handling
  database.py   — DB schema + queries
  security.py   — input cleaning, CSRF, decorators, helpers
  ai_model/     — Nour text analyzer (rule-based, no external API)
  static/       — CSS, JS, images (served with strong Cache-Control)
  templates/    — Jinja2 templates
"""
import os
import sys
import json
import time
import logging
import secrets
from datetime import datetime, date

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, make_response,
)

# Make local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    clean_text, clean_username, clean_digits, clean_date,
    csv_safe_cell, safe_compare, issue_csrf_token, rotate_csrf_token,
    verify_csrf, safe_referrer, session_fingerprint, client_ip,
    get_json_or_error, api_error, api_ok,
    login_required as _login_required_factory,
    role_required as _role_required_factory,
)

from database import (
    init_db, get_user_by_id, verify_login, register_user,
    update_user_profile, change_password,
    save_journal, get_student_journals, get_student_risk_history,
    get_student_personal_stats, count_today_journals,
    save_checkin, get_checkins, count_today_checkins,
    save_alert, save_survey, count_today_surveys,
    get_today_lecture, get_alerts_for_counselor, update_alert_status,
    get_students_for_counselor, counselor_update_student, get_school_stats,
    GRADES_AR, GRADES_EN, GRADES, rate_limit, get_supervised_grades_list,
    count_alerts_by_status, cleanup_rate_store,
    save_location, get_student_location, get_all_student_locations,
    save_goal, get_goals, update_goal, delete_goal,
    save_game_score, get_game_top_score,
    save_breathing_session, get_breathing_stats,
    get_streak, update_streak, get_achievements,
    check_and_award_achievements, BADGES,
    get_approved_tips, submit_tip,
    log_counselor_action, password_strength_score,
)
from ai_model.analyzer import (
    analyze_text, calculate_risk_score, analyze_survey, predict_risk_trend,
    get_companion_response, quick_classify, BREATHING_EXERCISE,
)
from ai_model.groq_service import call_groq_ai, is_available as groq_is_available

# ─────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("schoolmind")

# ─────────────────────────────────────────────────────────────────────────
# Application limits / constants
# ─────────────────────────────────────────────────────────────────────────
MAX_JOURNAL_LEN  = 5000
MAX_JOURNALS_DAY = 5
MAX_SURVEYS_DAY  = 3
MAX_CHECKINS_DAY = 1
MAX_GOALS_ACTIVE = 20
MAX_CHAT_HISTORY = 20
MAX_AVATAR_BYTES = 200_000
MAX_NOTE_LEN     = 500
RISK_THRESHOLD   = 5.0
SESSION_DAYS     = 7

# ─────────────────────────────────────────────────────────────────────────
# Flask app + configuration
# ─────────────────────────────────────────────────────────────────────────
app = Flask(__name__)


def _load_secret_key():
    """
    Load SECRET_KEY: env var first, then a persisted local file (dev),
    finally generate a fresh one (last resort — sessions won't survive restart).
    """
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key and len(env_key) >= 32:
        return env_key
    if env_key:
        log.warning("SECRET_KEY in env is too short; generating a stronger one.")
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secret_key")
    try:
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                stored = f.read().strip().decode("utf-8", "ignore")
                if len(stored) >= 32:
                    return stored
        new_key = secrets.token_hex(32)
        with open(key_path, "wb") as f:
            f.write(new_key.encode("utf-8"))
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return new_key
    except Exception as e:
        log.error("Failed to persist secret key: %s", e)
        return secrets.token_hex(32)


app.secret_key = _load_secret_key()

# Detect HTTPS (Render terminates SSL at edge, sets X-Forwarded-Proto)
USE_HTTPS = (
    os.environ.get("FORCE_HTTPS", "0") == "1"
    or os.environ.get("RENDER", "0") == "1"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY        = True,
    SESSION_COOKIE_SAMESITE        = "Lax",
    SESSION_COOKIE_SECURE          = USE_HTTPS,
    SESSION_COOKIE_NAME            = "_sm_s",
    MAX_CONTENT_LENGTH             = 5 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME     = 86400 * SESSION_DAYS,
    JSON_AS_ASCII                  = False,
    JSONIFY_PRETTYPRINT_REGULAR    = False,
    PREFERRED_URL_SCHEME           = "https" if USE_HTTPS else "http",
    SEND_FILE_MAX_AGE_DEFAULT      = 60 * 60 * 24 * 7,
    TEMPLATES_AUTO_RELOAD          = os.environ.get("FLASK_DEBUG", "0") == "1",
)

# Trust X-Forwarded-* when behind a proxy (Render).
if USE_HTTPS:
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    except ImportError:
        pass

# Optional: response compression
try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass

with app.app_context():
    init_db()


# ─────────────────────────────────────────────────────────────────────────
# Security headers
# ─────────────────────────────────────────────────────────────────────────
# Note on CSP: 'unsafe-inline' is kept for script-src because the existing
# templates use many inline event handlers (onclick, onsubmit, etc.).
# Rewriting all 28 templates to remove these is a larger refactor; instead
# we rely on Jinja2 autoescape + our clean_text() server-side sanitization
# to prevent XSS. Other directives are tightened:
#   - 'object-src' is 'none' (no Flash/legacy plugins)
#   - 'frame-src' is 'none', 'frame-ancestors' is 'self' (clickjacking)
#   - 'base-uri' and 'form-action' are locked to 'self'
# To further tighten CSP in the future, all onclick="..." handlers should
# be moved into addEventListener in static/js/*.js, then 'unsafe-inline'
# can be removed from script-src.
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
    "font-src 'self' fonts.gstatic.com cdn.jsdelivr.net data:; "
    "img-src 'self' data: blob: *.tile.openstreetmap.org; "
    "connect-src 'self' nominatim.openstreetmap.org; "
    "media-src 'self' data:; "
    "frame-src 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'; "
)


@app.after_request
def apply_security_headers(response):
    response.headers["X-Request-ID"]           = secrets.token_hex(8)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]        = "SAMEORIGIN"
    response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]     = (
        "geolocation=(self), camera=(), microphone=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = CSP_POLICY
    response.headers["Cross-Origin-Opener-Policy"]   = "same-origin"
    # Note: "same-site" (not same-origin) so the browser can still load our
    # own static assets and legitimate CDN resources.
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-DNS-Prefetch-Control"] = "off"
    response.headers["Origin-Agent-Cluster"] = "?1"
    response.headers["Vary"] = "Cookie, Accept-Language"
    if USE_HTTPS:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    # Cache strategy
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    elif request.path in ("/ping", "/health"):
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# ─────────────────────────────────────────────────────────────────────────
# Context processor
# ─────────────────────────────────────────────────────────────────────────
@app.context_processor
def template_context():
    issue_csrf_token()
    lang  = session.get("lang", "ar")
    theme = session.get("theme", "dark")
    avatar_b64 = ""
    try:
        if "user_id" in session:
            user = get_user_by_id(session["user_id"])
            if user and user["is_active"]:
                avatar_b64 = user["avatar_b64"] or ""
            else:
                csrf = session.get("csrf_token")
                session.clear()
                session["csrf_token"] = csrf
                session["lang"] = lang
                session["theme"] = theme
    except Exception as e:
        log.error("template_context error: %s", e)

    hour = datetime.now().hour
    if lang == "ar":
        greet = ("صباح الخير" if 5 <= hour < 12
                 else "مساء الخير" if 12 <= hour < 18
                 else "مساء النور")
    else:
        greet = ("Good Morning" if 5 <= hour < 12
                 else "Good Afternoon" if 12 <= hour < 18
                 else "Good Evening")

    QUOTES_AR = [
        "كل يوم تكتب فيه هو انتصار 🌟", "مشاعرك تستحق أن تُسمع 💙",
        "أنت أقوى مما تعتقد 💪", "خطوة صغيرة كل يوم = فارق كبير 🚀",
        "الاهتمام بصحتك النفسية أذكى شيء تفعله 🧠", "لا بأس بأن تطلب المساعدة 🤝",
        "أنت لست وحدك في هذا 💜", "الأيام الصعبة تنتهي دائماً ☀️",
    ]
    QUOTES_EN = [
        "Every day you write is a victory 🌟", "Your feelings deserve to be heard 💙",
        "You are stronger than you think 💪", "One small step daily = a big difference 🚀",
        "Mental health care is the smartest thing 🧠", "It's okay to ask for help 🤝",
        "You are not alone 💜", "Hard days always end ☀️",
    ]
    pool = QUOTES_AR if lang == "ar" else QUOTES_EN
    quote = pool[date.today().toordinal() % len(pool)]

    return dict(
        grades=GRADES_AR if lang == "ar" else GRADES_EN,
        all_grades=GRADES,
        session=session,
        csrf_token=session.get("csrf_token", ""),
        lang=lang,
        theme=theme,
        greeting=greet,
        unread_badges=session.get("new_badges_count", 0),
        daily_quote=quote,
        avatar_b64=avatar_b64,
    )


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
def _lang():  return session.get("lang", "ar")
def _theme(): return session.get("theme", "dark")
def _supervised_grades(): return get_supervised_grades_list(
    session.get("supervised_grades", "[]"))


def _save_session(user):
    """Persist a logged-in user into the Flask session, with session rotation."""
    lang  = session.get("lang", "ar")
    theme = session.get("theme", "dark")
    session.clear()
    try:
        is_anon = bool(user["is_anonymous"])
    except (KeyError, IndexError):
        is_anon = False
    session.update(
        lang=lang, theme=theme,
        user_id=user["id"], username=user["username"], role=user["role"],
        display_name=user["display_name"] or "",
        anonymous_code=user["anonymous_code"] or "",
        is_anonymous=is_anon,
        grade=user["grade"] or "",
        supervised_grades=user["supervised_grades"] or "[]",
        _fp=session_fingerprint(),
        new_badges_count=0,
    )
    session.permanent = True
    rotate_csrf_token()


# Bind decorators
login_required     = _login_required_factory(get_user_by_id)
counselor_required = _role_required_factory("counselor", get_user_by_id)


# ─────────────────────────────────────────────────────────────────────────
# Nour reply helper — tries Groq first, falls back to local engine
# Safety is always enforced BEFORE the AI call, not trusted to the AI.
# ─────────────────────────────────────────────────────────────────────────
# Crisis keywords — if ANY of these appears, we always append a safety
# footer to the reply regardless of what the AI says. This guarantees the
# student sees emergency resources even if the model forgets.
_CRISIS_PATTERNS = (
    # Arabic
    "انتحار", "أنتحر", "بدي موت", "بدي أموت", "ابغى اموت", "اموت",
    "اقتل نفسي", "أقتل نفسي", "أذية نفسي", "أؤذي نفسي", "اذية نفسي",
    "مالي قيمة", "ما في أمل", "حياتي ما لها طعم", "بتمنى أموت",
    "أكره نفسي", "اكره حالي", "أريد أن أموت",
    # English
    "kill myself", "killing myself", "suicide", "suicidal", "end my life",
    "don't want to live", "want to die", "wanna die", "hurt myself",
    "hurting myself", "self harm", "self-harm", "cutting myself",
    "better off dead", "no reason to live",
)

_CRISIS_FOOTER_AR = (
    "\n\n⚠️ أنا قلقان عليك الآن. لو بتمرّ بلحظة صعبة جداً، أرجوك اتصل فوراً بـ 911 "
    "أو تحدّث مع شخص بالغ تثق به الآن. أنت مهم، ومساعدتك ممكنة."
)
_CRISIS_FOOTER_EN = (
    "\n\n⚠️ I'm worried about you right now. If you're in a very hard moment, "
    "please call 911 right now or talk to a trusted adult. You matter, and help is possible."
)


def _check_crisis(message):
    """Return True if message contains a crisis keyword."""
    if not message:
        return False
    low = message.lower()
    return any(p in low for p in _CRISIS_PATTERNS)


def _nour_reply(message, lang, emotion, history):
    """
    Get a chat reply for the user.

    Safety-first flow:
      1. Check for crisis keywords. If present, we'll append a safety footer
         to whatever reply we generate (AI or local).
      2. Try Groq AI if GROQ_API_KEY is set and the call succeeds.
      3. Otherwise fall back to the local rule-based `get_companion_response`.

    Returns: (reply_text, source)
    """
    is_crisis = _check_crisis(message)

    # Try Groq first
    reply = None
    source = "local"
    if groq_is_available():
        reply = call_groq_ai(message, lang=lang, emotion=emotion, history=history)
        if reply:
            source = "groq"

    # Fallback to local engine
    if not reply:
        reply = get_companion_response(emotion, lang, message, history=history)
        source = "local"

    # Always append crisis footer if triggered
    if is_crisis:
        footer = _CRISIS_FOOTER_AR if lang == "ar" else _CRISIS_FOOTER_EN
        reply = reply + footer

    return reply, source


# ─────────────────────────────────────────────────────────────────────────
# Utility routes
# ─────────────────────────────────────────────────────────────────────────
@app.route("/set-lang/<lang>")
def set_lang(lang):
    session["lang"] = lang if lang in ("ar", "en") else "ar"
    return redirect(safe_referrer())


@app.route("/set-theme/<theme>")
def set_theme(theme):
    session["theme"] = theme if theme in ("light", "dark") else "dark"
    return redirect(safe_referrer())


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Disallow: /student\n"
        "Disallow: /counselor\n"
        "Disallow: /api\n"
        "Disallow: /journal\n"
        "Disallow: /companion\n"
    )
    return make_response(body, 200, {"Content-Type": "text/plain; charset=utf-8"})


@app.route("/sitemap.xml")
def sitemap():
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>/</loc></url>\n'
        '  <url><loc>/login</loc></url>\n'
        '</urlset>\n'
    )
    return make_response(body, 200, {"Content-Type": "application/xml; charset=utf-8"})


@app.route("/ping")
def ping():
    import random
    if random.random() < 0.05:
        try:
            cleanup_rate_store()
            from database import get_db
            conn = get_db()
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conn.execute(
                "DELETE FROM lecture_log WHERE id NOT IN "
                "(SELECT id FROM lecture_log ORDER BY shown_at DESC LIMIT 1000)"
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
    return jsonify({"status": "ok", "version": "v21", "ts": int(time.time())}), 200


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "v21",
                    "ai": "nour_local", "ts": int(time.time())})


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for(
            "counselor_dashboard" if session.get("role") == "counselor"
            else "student_dashboard"
        ))
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if request.form.get("honeypot"):
            log.warning("Honeypot triggered ip=%s", client_ip())
            return redirect(url_for("login"))
        if not rate_limit(f"login:{client_ip()}", 10, 60):
            flash("محاولات كثيرة، حاول لاحقاً" if lang == "ar"
                  else "Too many attempts, try later", "error")
            return render_template("login.html", lang=lang, theme=_theme())
        username = clean_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        if not username or not password:
            flash("يرجى إدخال البيانات" if lang == "ar" else "Enter credentials", "error")
            return render_template("login.html", lang=lang, theme=_theme())
        user = verify_login(username, password)
        if user:
            _save_session(user)
            try:
                check_and_award_achievements(user["id"])
            except Exception as e:
                log.error("login award error: %s", e)
            return redirect(url_for(
                "counselor_dashboard" if user["role"] == "counselor"
                else "student_dashboard"
            ))
        time.sleep(0.18)
        flash("بيانات الدخول غير صحيحة" if lang == "ar" else "Invalid credentials", "error")
    return render_template("login.html", lang=lang, theme=_theme())


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if request.form.get("honeypot"):
            return redirect(url_for("register"))
        if not rate_limit(f"reg:{client_ip()}", 5, 300):
            flash("محاولات كثيرة", "error")
            return render_template("register.html", lang=lang, theme=_theme())
        role = request.form.get("role", "student")
        if role not in ("student", "counselor"):
            flash("دور غير صالح", "error")
            return render_template("register.html", lang=lang, theme=_theme())
        username = clean_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        name     = clean_text(request.form.get("display_name", ""), 120)
        grade    = request.form.get("grade") if role == "student" else None
        sup      = ([g for g in request.form.getlist("supervised_grades") if g in GRADES]
                    if role == "counselor" else None)
        nid      = clean_digits(request.form.get("national_id", "")) or None
        bday     = clean_date(request.form.get("birthdate", "")) or None

        if password and password.lower() == username.lower():
            flash("كلمة المرور لا تكون اسم المستخدم", "error")
            return render_template("register.html", lang=lang, theme=_theme())
        if grade and grade not in GRADES:
            flash("الصف غير صالح", "error")
            return render_template("register.html", lang=lang, theme=_theme())
        if password != confirm:
            flash("كلمات المرور غير متطابقة", "error")
            return render_template("register.html", lang=lang, theme=_theme())

        ok, result = register_user(username, password, role, name, grade, sup, nid, bday)
        if ok:
            user = get_user_by_id(result)
            _save_session(user)
            check_and_award_achievements(result)
            flash("أهلاً بك! 🎉" if lang == "ar" else "Welcome! 🎉", "success")
            return redirect(url_for(
                "counselor_dashboard" if role == "counselor"
                else "student_dashboard"
            ))
        flash(result, "error")
    return render_template("register.html", lang=lang, theme=_theme())


@app.route("/register/anonymous", methods=["GET", "POST"])
def register_anonymous():
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if not rate_limit(f"reg_anon:{client_ip()}", 6, 300):
            flash("محاولات كثيرة", "error")
            return render_template("register_anon.html", lang=lang, theme=_theme())
        import string as _s
        ru = "anon_" + "".join(secrets.choice(_s.digits) for _ in range(6))
        rp = secrets.token_urlsafe(10)
        name  = clean_text(request.form.get("display_name", "مجهول الهوية"), 60)
        grade = request.form.get("grade") or GRADES_AR[0]
        if grade not in GRADES:
            grade = GRADES_AR[0]
        ok, result = register_user(ru, rp, "student", name, grade, is_anonymous=True)
        if ok:
            user = get_user_by_id(result)
            _save_session(user)
            session["anon_password"] = rp
            flash("تم إنشاء حساب مجهول ✅", "success")
            return redirect(url_for("student_dashboard"))
        flash(result, "error")
    return render_template("register_anon.html", lang=lang, theme=_theme())


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Verifies username + national_id + birthdate.
    Issues a one-time temporary password shown on the NEXT page view only
    (NOT flashed into the URL/history).
    """
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if not rate_limit(f"forgot:{client_ip()}", 3, 300):
            flash("محاولات كثيرة" if lang == "ar" else "Too many attempts", "error")
            return render_template("forgot_password.html", lang=lang, theme=_theme())
        username = clean_username(request.form.get("username", ""))
        from database import get_db
        conn = get_db()
        u = conn.execute(
            "SELECT id, username, national_id, birthdate FROM users "
            "WHERE username=? AND is_active=1",
            (username,)
        ).fetchone()
        conn.close()
        if u and u["national_id"] and u["birthdate"]:
            nid  = clean_digits(request.form.get("national_id", ""))
            bday = clean_date(request.form.get("birthdate", ""))
            if (safe_compare(nid, u["national_id"] or "") and
                safe_compare(bday, u["birthdate"] or "")):
                temp_pw = secrets.token_urlsafe(10)
                ok, _ = change_password(u["id"], temp_pw)
                if ok:
                    log.info("Password reset issued uid=%s ip=%s",
                             u["id"], client_ip())
                    return render_template(
                        "forgot_password.html",
                        lang=lang, theme=_theme(),
                        temp_password=temp_pw, success_user=u["username"],
                    )
        time.sleep(0.25)
        flash(
            "إذا كانت البيانات صحيحة سيتم إصدار كلمة مرور مؤقتة"
            if lang == "ar"
            else "If credentials match, a temporary password will be issued",
            "info",
        )
    return render_template("forgot_password.html", lang=lang, theme=_theme())


@app.route("/logout")
def logout():
    lang  = session.get("lang", "ar")
    theme = session.get("theme", "dark")
    session.clear()
    session["lang"]  = lang
    session["theme"] = theme
    rotate_csrf_token()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────────────────
# Student — dashboard, stats, profile
# ─────────────────────────────────────────────────────────────────────────
@app.route("/student")
@login_required
def student_dashboard():
    uid  = session["user_id"]
    lang = _lang()
    try:
        user = get_user_by_id(uid)
        if not user:
            session.clear()
            return redirect(url_for("login"))
        journals = get_student_journals(uid, limit=5)
        history  = get_student_risk_history(uid, days=30)
        checkins = get_checkins(uid, limit=7)
        scores = [r["risk_score"] for r in history if r["risk_score"] is not None]
        labels = [r["created_at"][:10] for r in history]
        prediction = predict_risk_trend(scores) if len(scores) >= 3 else None
        latest = round(scores[-1], 1) if scores else 0
        if   latest >= 7.5: level = "critical"
        elif latest >= 5.0: level = "high"
        elif latest >= 2.5: level = "medium"
        else:               level = "low"
        lecture = get_today_lecture(uid)
        streak  = get_streak(uid)
        badges  = get_achievements(uid)[:3]
        return render_template(
            "student_dashboard.html",
            user=user, journals=journals, checkins=checkins,
            chart_scores=json.dumps(scores), chart_labels=json.dumps(labels),
            prediction=prediction, latest_risk=latest, risk_level=level,
            lecture=lecture, streak=streak, achievements=badges,
            lang=lang, theme=_theme(),
        )
    except Exception as e:
        log.error("student_dashboard error: %s", e)
        flash("حدث خطأ في تحميل لوحة التحكم" if lang == "ar"
              else "Dashboard loading error", "error")
        return redirect(url_for("login"))


@app.route("/student/stats")
@login_required
def student_stats():
    uid = session["user_id"]
    stats = get_student_personal_stats(uid)
    history = get_student_risk_history(uid, days=60)
    scores = [r["risk_score"] for r in history if r["risk_score"] is not None]
    labels = [r["created_at"][:10] for r in history]
    sk = get_streak(uid)
    stats["current_streak"] = sk["current"]
    stats["longest_streak"] = sk["longest"]
    checkins = get_checkins(uid, limit=30)
    mood_data = [{"date": c["created_at"][:10], "mood": c["mood"]}
                 for c in checkins if c["created_at"]]
    return render_template(
        "student_stats.html",
        stats=stats,
        chart_scores=json.dumps(scores),
        chart_labels=json.dumps(labels),
        mood_data=json.dumps(mood_data),
        lang=_lang(), theme=_theme(),
    )


@app.route("/student/profile", methods=["GET", "POST"])
@login_required
def student_profile():
    uid  = session["user_id"]
    lang = _lang()
    user = get_user_by_id(uid)
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        action = request.form.get("action", "")
        if action == "update_info":
            name = clean_text(request.form.get("display_name", ""), 120)
            nid  = clean_digits(request.form.get("national_id", "")) or None
            bday = clean_date(request.form.get("birthdate", "")) or None
            if name:
                update_user_profile(uid, display_name=name,
                                    national_id=nid, birthdate=bday)
                session["display_name"] = name
                flash("تم التحديث ✅" if lang == "ar" else "Updated ✅", "success")
            else:
                flash("الاسم مطلوب" if lang == "ar" else "Name required", "error")
        elif action == "change_password":
            old  = request.form.get("old_password", "")
            new  = request.form.get("new_password", "")
            conf = request.form.get("confirm_new_password", "")
            if not verify_login(user["username"], old):
                flash("كلمة المرور الحالية خاطئة" if lang == "ar"
                      else "Wrong current password", "error")
            elif new != conf:
                flash("كلمات المرور غير متطابقة", "error")
            elif new.lower() == user["username"].lower():
                flash("كلمة المرور لا تكون اسم المستخدم", "error")
            else:
                ok, err = change_password(uid, new)
                flash("تم التغيير ✅" if ok else err,
                      "success" if ok else "error")
        elif action == "upload_avatar":
            _handle_avatar_upload(uid, lang)
        elif action == "delete_avatar":
            update_user_profile(uid, avatar_b64="")
            flash("تم حذف الصورة", "info")
        user = get_user_by_id(uid)
    return render_template("student_profile.html",
                           user=user, lang=lang, theme=_theme())


def _handle_avatar_upload(uid, lang):
    """Validate + store user-uploaded avatar (max 200 KB, image only)."""
    f = request.files.get("avatar")
    if not f or not f.filename:
        flash("لم يتم اختيار ملف" if lang == "ar" else "No file selected", "error")
        return
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        flash("يُسمح JPG/PNG/WebP فقط", "error")
        return
    data = f.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        flash("الصورة كبيرة جداً (حد 200KB)", "error")
        return
    sig_map = {b"\xff\xd8\xff": "jpeg", b"\x89PNG": "png", b"RIFF": "webp"}
    detected = next((mime for sig, mime in sig_map.items()
                     if data[:len(sig)] == sig), None)
    if not detected:
        flash("ملف غير صالح", "error")
        return
    if detected == "webp" and b"WEBP" not in data[:24]:
        flash("ملف WEBP غير صالح", "error")
        return
    import base64 as _b
    b64 = f"data:image/{detected};base64," + _b.b64encode(data).decode()
    update_user_profile(uid, avatar_b64=b64)
    flash("تم تحديث الصورة ✅", "success")


# ─────────────────────────────────────────────────────────────────────────
# Student — journal, survey, check-in, companion
# ─────────────────────────────────────────────────────────────────────────
@app.route("/journal", methods=["GET", "POST"])
@login_required
def journal():
    uid  = session["user_id"]
    lang = _lang()
    analysis_result = None
    risk_result     = None
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        content = clean_text(request.form.get("content", ""), MAX_JOURNAL_LEN)
        try:
            mood = max(1, min(5, int(request.form.get("mood_score", 3))))
        except (TypeError, ValueError):
            mood = 3
        today_count = count_today_journals(uid)
        if today_count >= MAX_JOURNALS_DAY:
            flash(f"الحد الأقصى {MAX_JOURNALS_DAY} يوميات/يوم", "error")
        elif len(content) < 5:
            flash("يجب كتابة 5 أحرف على الأقل", "error")
        elif len(content) > MAX_JOURNAL_LEN:
            flash(f"النص طويل (الحد {MAX_JOURNAL_LEN})", "error")
        else:
            try:
                analysis = analyze_text(content)
                past_scores = [r["risk_score"] for r in get_student_risk_history(uid)
                               if r["risk_score"] is not None]
                risk = calculate_risk_score(analysis, past_scores)
                save_journal(uid, content, mood, analysis.get("lang", lang),
                             analysis, risk, "", "", "nour_local")
                sr = update_streak(uid)
                nb = check_and_award_achievements(uid)
                session["new_badges_count"] = len(nb)
                session.modified = True
                if risk.get("should_alert"):
                    u = get_user_by_id(uid)
                    save_alert(uid, u["anonymous_code"] or "S-????",
                               u["grade"] or "", risk, analysis, lang)
                if sr.get("new_badge") or nb:
                    lbl = (sr.get("new_badge") or {}).get(
                        "label_ar" if lang == "ar" else "label_en", ""
                    )
                    if lbl:
                        flash(f"🎉 {'إنجاز جديد:' if lang=='ar' else 'Achievement:'} {lbl}",
                              "badge")
                analysis_result = {**analysis, "ai_summary": "",
                                   "ai_advice": "", "source": "nour_local"}
                risk_result = risk
            except Exception as e:
                log.error("journal save error: %s", e)
                flash("حدث خطأ في التحليل", "warning")
    recent = get_student_journals(uid, limit=8)
    today_count = count_today_journals(uid)
    return render_template(
        "journal.html",
        analysis=analysis_result, risk=risk_result,
        recent_journals=recent, today_count=today_count,
        max_journals=MAX_JOURNALS_DAY, max_length=MAX_JOURNAL_LEN,
        lang=lang, theme=_theme(),
    )


@app.route("/survey", methods=["GET", "POST"])
@login_required
def survey():
    uid  = session["user_id"]
    lang = _lang()
    result = None
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if count_today_surveys(uid) >= MAX_SURVEYS_DAY:
            flash(f"الحد الأقصى {MAX_SURVEYS_DAY} استبيانات/يوم", "error")
            return render_template("survey.html", lang=lang,
                                   theme=_theme(), result=None)
        answers = {}
        for i in range(1, 21):
            try:
                v = int(request.form.get(f"q{i}", 3) or 3)
                answers[f"q{i}"] = max(1, min(5, v))
            except (TypeError, ValueError):
                answers[f"q{i}"] = 3
        notes = clean_text(request.form.get("notes", ""), MAX_NOTE_LEN)
        result = analyze_survey(answers)
        result["max_score"] = 10
        save_survey(uid, answers, notes)
        check_and_award_achievements(uid)
        if result.get("should_alert"):
            u = get_user_by_id(uid)
            save_alert(
                uid, u["anonymous_code"] or "S-????", u["grade"] or "",
                {"score": result["score"], "level": result["level"], "max_score": 10},
                {"dominant_emotion": result.get("dominant_concern", "neutral"),
                 "has_bullying": False},
                lang,
            )
    return render_template("survey.html", lang=lang, theme=_theme(), result=result)


@app.route("/checkin", methods=["POST"])
@login_required
def checkin():
    chk = verify_csrf()
    if chk: return chk
    uid  = session["user_id"]
    lang = _lang()
    if count_today_checkins(uid) >= MAX_CHECKINS_DAY:
        flash("✅ سجّلت حالتك اليوم", "info")
        return redirect(url_for("student_dashboard"))
    try:
        mood = max(1, min(5, int(
            request.form.get("mood_score") or request.form.get("mood") or 3
        )))
    except (TypeError, ValueError):
        mood = 3
    notes = clean_text(request.form.get("notes", ""), MAX_NOTE_LEN)
    save_checkin(uid, mood,
                 int(bool(request.form.get("feeling_safe"))),
                 int(bool(request.form.get("feeling_lonely"))),
                 notes)
    sr = update_streak(uid)
    nb = check_and_award_achievements(uid)
    session["new_badges_count"] = len(nb)
    session.modified = True
    if sr.get("new_badge"):
        b = sr["new_badge"]
        lbl = b.get("label_ar" if lang == "ar" else "label_en", "إنجاز!")
        flash(f"🔥 {lbl} · ستريك {sr['current']} يوم!", "success")
    elif sr.get("incremented"):
        flash(f"✅ تم التسجيل · 🔥 ستريك {sr['current']} يوم", "success")
    else:
        flash("✅ تم تسجيل حالتك", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/companion", methods=["GET", "POST"])
@login_required
def companion():
    lang = _lang()
    response = emotion = breathing = None
    if "chat_history" not in session:
        session["chat_history"] = []
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if not rate_limit(f"comp:{client_ip()}", 30, 60):
            flash("محاولات كثيرة", "error")
            return render_template(
                "companion.html",
                response=None, emotion=None, breathing=None, has_ai=True,
                chat_history=session.get("chat_history", []),
                lang=lang, theme=_theme(),
            )
        msg = clean_text(request.form.get("message", ""), 1000)
        if msg:
            classified = quick_classify(msg)
            emotion = classified.get("dominant_emotion", "neutral")
            history = list(session.get("chat_history", []))
            response, source = _nour_reply(msg, lang, emotion, history)
            history.append({"role": "user",      "content": msg})
            history.append({"role": "assistant", "content": response})
            session["chat_history"] = history[-(MAX_CHAT_HISTORY * 2):]
            session.modified = True
            if any(w in msg.lower() for w in ["تنفس", "breath", "تمرين", "calm", "هدئ"]):
                breathing = BREATHING_EXERCISE.get(lang, BREATHING_EXERCISE["ar"])
    return render_template(
        "companion.html",
        response=response, emotion=emotion, breathing=breathing,
        has_ai=True, chat_history=session.get("chat_history", []),
        lang=lang, theme=_theme(),
    )


@app.route("/companion/reset", methods=["POST"])
@login_required
def companion_reset():
    chk = verify_csrf()
    if chk: return chk
    session["chat_history"] = []
    session.modified = True
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────
# Student — static-ish content pages
# ─────────────────────────────────────────────────────────────────────────
@app.route("/emergency")
@login_required
def emergency():
    return render_template("emergency.html", lang=_lang(), theme=_theme())


@app.route("/resources")
@login_required
def resources():
    return render_template("resources.html", lang=_lang(), theme=_theme())


@app.route("/games")
@login_required
def games():
    uid = session["user_id"]
    game_ids = ("breathing", "memory", "positive", "quiz", "emoji_match",
                "star_catch", "gratitude", "color_mood", "reaction", "affirmation")
    top_scores = {g: get_game_top_score(uid, g) for g in game_ids}
    return render_template("games.html", lang=_lang(), theme=_theme(),
                           top_scores=top_scores)


@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    uid  = session["user_id"]
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        action = request.form.get("action", "add")
        if action == "add":
            title = clean_text(request.form.get("title", ""), 200)
            desc  = clean_text(request.form.get("description", ""), 1000)
            cat   = request.form.get("category", "personal")
            if cat not in ("personal", "study", "health", "social", "habit"):
                cat = "personal"
            tdate = clean_date(request.form.get("target_date", "")) or None
            if not title:
                flash("عنوان الهدف مطلوب", "error")
            elif len(get_goals(uid, status="active")) >= MAX_GOALS_ACTIVE:
                flash(f"الحد الأقصى {MAX_GOALS_ACTIVE} هدف", "error")
            else:
                save_goal(uid, title, desc, cat, tdate)
                check_and_award_achievements(uid)
                flash("تم إضافة الهدف ✅", "success")
        elif action == "update_progress":
            try:
                gid  = int(request.form.get("goal_id", 0) or 0)
                prog = min(100, max(0, int(request.form.get("progress", 0) or 0)))
            except (TypeError, ValueError):
                return redirect(url_for("goals"))
            update_goal(gid, uid, progress=prog)
            if prog >= 100:
                update_goal(gid, uid, status="completed")
                check_and_award_achievements(uid)
                flash("🎉 أُنجز الهدف!", "success")
        elif action == "complete":
            try:
                gid = int(request.form.get("goal_id", 0) or 0)
            except (TypeError, ValueError):
                return redirect(url_for("goals"))
            update_goal(gid, uid, status="completed", progress=100)
            check_and_award_achievements(uid)
            flash("🎉 تهانينا!", "success")
        elif action == "delete":
            try:
                gid = int(request.form.get("goal_id", 0) or 0)
            except (TypeError, ValueError):
                return redirect(url_for("goals"))
            delete_goal(gid, uid)
            flash("تم الحذف", "info")
        return redirect(url_for("goals"))
    all_goals = get_goals(uid)
    active = [g for g in all_goals if g["status"] == "active"]
    done   = [g for g in all_goals if g["status"] == "completed"]
    return render_template(
        "goals.html", lang=lang, theme=_theme(),
        active_goals=active, done_goals=done,
        total=len(all_goals), completed=len(done),
        max_goals=MAX_GOALS_ACTIVE,
    )


@app.route("/breathing-center")
@login_required
def breathing_center():
    uid = session["user_id"]
    return render_template("breathing_center.html",
                           lang=_lang(), theme=_theme(),
                           stats=get_breathing_stats(uid))


@app.route("/achievements")
@login_required
def achievements():
    uid = session["user_id"]
    check_and_award_achievements(uid)
    badges = get_achievements(uid)
    sk = get_streak(uid)
    session["new_badges_count"] = 0
    session.modified = True
    return render_template("achievements.html",
                           lang=_lang(), theme=_theme(),
                           badges=badges, streak=sk, all_badge_defs=BADGES)


@app.route("/about")
@login_required
def about():
    return render_template("about.html", lang=_lang(), theme=_theme())


@app.route("/accessibility")
@login_required
def accessibility():
    return render_template("accessibility.html", lang=_lang(), theme=_theme())


@app.route("/mood-diary")
@login_required
def mood_diary():
    uid = session["user_id"]
    checkins = get_checkins(uid, limit=30)
    return render_template("mood_diary.html", lang=_lang(), theme=_theme(),
                           checkins=checkins)


@app.route("/daily-tips")
@login_required
def daily_tips():
    tips = get_approved_tips(30)
    return render_template("daily_tips.html", lang=_lang(), theme=_theme(), tips=tips)


@app.route("/relaxation")
@login_required
def relaxation():
    return render_template("relaxation.html", lang=_lang(), theme=_theme())


# ─────────────────────────────────────────────────────────────────────────
# Counselor routes
# ─────────────────────────────────────────────────────────────────────────
@app.route("/counselor")
@counselor_required
def counselor_dashboard():
    try:
        sg     = _supervised_grades()
        sts    = get_students_for_counselor(sg or None)
        alerts = get_alerts_for_counselor(sg or None, limit=30)
        stats  = get_school_stats(sg)
        new_alerts = sum(1 for a in alerts if a["status"] == "new")
        low  = sum(1 for s in sts if not s["latest_level"] or s["latest_level"] == "low")
        med  = sum(1 for s in sts if s["latest_level"] == "medium")
        high = sum(1 for s in sts if s["latest_level"] in ("high", "critical"))
        return render_template(
            "counselor_dashboard.html",
            students=sts, alerts=alerts, stats=stats,
            new_alerts=new_alerts,
            chart_dist=json.dumps([low, med, high]),
            supervised_grades=sg,
            lang=_lang(), theme=_theme(),
        )
    except Exception as e:
        log.error("counselor_dashboard error: %s", e)
        flash("حدث خطأ في تحميل لوحة التحكم", "error")
        return redirect(url_for("login"))


@app.route("/counselor/profile", methods=["GET", "POST"])
@counselor_required
def counselor_profile():
    uid = session["user_id"]
    user = get_user_by_id(uid)
    lang = _lang()
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        action = request.form.get("action", "")
        if action == "update_info":
            name = clean_text(request.form.get("display_name", ""), 120)
            nid  = clean_digits(request.form.get("national_id", "")) or None
            bday = clean_date(request.form.get("birthdate", "")) or None
            if name:
                update_user_profile(uid, display_name=name,
                                    national_id=nid, birthdate=bday)
                session["display_name"] = name
                flash("تم التحديث ✅", "success")
        elif action == "change_password":
            op = request.form.get("old_password", "")
            np = request.form.get("new_password", "")
            cp = request.form.get("confirm_new_password", "")
            if not verify_login(user["username"], op):
                flash("كلمة المرور الحالية خاطئة", "error")
            elif np != cp:
                flash("كلمات المرور غير متطابقة", "error")
            else:
                ok, err = change_password(uid, np)
                flash("تم التغيير ✅" if ok else err,
                      "success" if ok else "error")
        user = get_user_by_id(uid)
    return render_template("counselor_profile.html",
                           user=user, lang=lang, theme=_theme())


@app.route("/counselor/students")
@counselor_required
def counselor_students():
    sg = _supervised_grades()
    grade_filter = request.args.get("grade", "")
    students = get_students_for_counselor(sg or None)
    if grade_filter and grade_filter in GRADES:
        students = [s for s in students if s["grade"] == grade_filter]
    return render_template(
        "counselor_students.html",
        students=students, supervised_grades=sg,
        grade_filter=grade_filter,
        lang=_lang(), theme=_theme(),
    )


@app.route("/counselor/students/<int:uid>/edit", methods=["GET", "POST"])
@counselor_required
def counselor_edit_student(uid):
    st = get_user_by_id(uid)
    if not st:
        flash("الطالب غير موجود", "error")
        return redirect(url_for("counselor_students"))
    # Authorization check: counselor can only edit students in their grades
    if st["role"] != "student":
        flash("لا يمكن تعديل هذا المستخدم", "error")
        return redirect(url_for("counselor_students"))
    sg = _supervised_grades()
    if sg and st["grade"] not in sg:
        log.warning("Unauthorized counselor edit attempt counselor=%s target=%s",
                    session["user_id"], uid)
        flash("لا يمكنك تعديل طالب خارج نطاق إشرافك", "error")
        return redirect(url_for("counselor_students"))

    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        counselor_update_student(
            uid,
            new_username=(clean_username(request.form.get("username", "")) or None),
            new_password=(request.form.get("new_password", "").strip() or None),
            new_display_name=(clean_text(request.form.get("display_name", ""), 120)
                              or None),
        )
        log_counselor_action(session["user_id"], "edit_student", f"uid={uid}")
        flash("تم التحديث ✅", "success")
        return redirect(url_for("counselor_students"))
    return render_template("counselor_edit_student.html",
                           student=st, lang=_lang(), theme=_theme())


@app.route("/counselor/student/<int:uid>")
@counselor_required
def student_detail(uid):
    user = get_user_by_id(uid)
    if not user:
        flash("الطالب غير موجود", "error")
        return redirect(url_for("counselor_dashboard"))
    if user["role"] != "student":
        flash("هذا الحساب ليس طالباً", "error")
        return redirect(url_for("counselor_dashboard"))
    sg = _supervised_grades()
    if sg and user["grade"] not in sg:
        log.warning("Unauthorized detail view counselor=%s target=%s",
                    session["user_id"], uid)
        flash("خارج نطاق إشرافك", "error")
        return redirect(url_for("counselor_students"))
    journals = get_student_journals(uid, limit=20)
    history  = get_student_risk_history(uid, days=30)
    scores   = [r["risk_score"] for r in history if r["risk_score"] is not None]
    labels   = [r["created_at"][:10] for r in history]
    prediction = predict_risk_trend(scores) if len(scores) >= 3 else None
    personal = get_student_personal_stats(uid)
    loc      = get_student_location(uid)
    sk       = get_streak(uid)
    return render_template(
        "student_detail.html",
        student=user, journals=journals, personal_stats=personal,
        chart_scores=json.dumps(scores), chart_labels=json.dumps(labels),
        prediction=prediction, location=loc, streak=sk,
        lang=_lang(), theme=_theme(),
    )


@app.route("/counselor/alert/<int:aid>/update", methods=["POST"])
@counselor_required
def update_alert(aid):
    chk = verify_csrf()
    if chk: return chk
    status = request.form.get("status", "reviewed")
    if status not in ("new", "reviewed", "handled"):
        status = "reviewed"
    update_alert_status(aid, status)
    log_counselor_action(session["user_id"], "update_alert",
                         f"id={aid} status={status}")
    flash("تم التحديث ✅", "success")
    return redirect(url_for("counselor_dashboard"))


@app.route("/counselor/export-csv")
@counselor_required
def export_csv():
    import csv, io
    from datetime import datetime as _dt
    sg = _supervised_grades()
    students = get_students_for_counselor(sg or None)
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel UTF-8 compatibility
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "الرمز", "الصف", "اليوميات", "درجة الخطر",
        "مستوى الخطر", "ستريك", "آخر تسجيل",
    ])
    for s in students:
        writer.writerow([
            csv_safe_cell(s["anonymous_code"] or ""),
            csv_safe_cell(s["grade"] or ""),
            csv_safe_cell(s["journal_count"] or 0),
            csv_safe_cell(round(s["latest_risk"] or 0, 1)),
            csv_safe_cell(s["latest_level"] or "low"),
            csv_safe_cell(
                s["current_streak"] if "current_streak" in s.keys() else 0
            ),
            csv_safe_cell((s["last_entry"] or "")[:10]),
        ])
    filename = f"students_{_dt.now():%Y%m%d_%H%M}.csv"
    resp = make_response(buf.getvalue())
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    log_counselor_action(session["user_id"], "export_csv",
                         f"n={len(students)}")
    return resp


@app.route("/counselor/locations")
@counselor_required
def counselor_locations():
    sg = _supervised_grades()
    locs = get_all_student_locations(sg if sg else None)
    locs_json = json.dumps([{
        "lat": l["latitude"], "lng": l["longitude"],
        "code": l["anonymous_code"] or "S-????",
        "grade": l["grade"] or "",
        "time": (l["shared_at"] or "")[:16],
        "city": l["city"] or "",
        "uid":  l["user_id"],
    } for l in locs])
    return render_template("counselor_locations.html",
                           locations=locs, locs_json=locs_json,
                           lang=_lang(), theme=_theme())


@app.route("/school-map")
@login_required
def school_map():
    if session.get("role") == "counselor":
        sg = _supervised_grades()
        stats = get_school_stats(sg if sg else None)
        return render_template("school_map.html",
                               stats=stats, role="counselor",
                               lang=_lang(), theme=_theme())
    return redirect(url_for("student_stats"))


# ─────────────────────────────────────────────────────────────────────────
# API routes
# ─────────────────────────────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    chk = verify_csrf()
    if chk: return chk
    if not rate_limit(f"api:{client_ip()}", 60, 60):
        return api_error("rate limited", 429)
    data, err = get_json_or_error()
    if err: return err
    text = clean_text(data.get("text", ""), 5000)
    if len(text) < 3:
        return api_error("too short")
    try:
        return jsonify(analyze_text(text))
    except Exception as e:
        log.error("api_analyze error: %s", e)
        return api_error("failed", 500)


@app.route("/api/companion", methods=["POST"])
@login_required
def api_companion():
    chk = verify_csrf()
    if chk: return chk
    uid = session.get("user_id", "x")
    if not rate_limit(f"comp:{client_ip()}", 30, 60):
        return api_error("rate limited", 429)
    if not rate_limit(f"comp_u:{uid}", 60, 300):
        return api_error("rate limited", 429)
    data, err = get_json_or_error()
    if err: return err
    msg = clean_text(data.get("message", ""), 1000)
    if not msg:
        return api_error("empty")
    lang = _lang()
    lc = quick_classify(msg)
    emotion = lc.get("dominant_emotion", "neutral")
    history = list(session.get("chat_history", []))
    response, _source = _nour_reply(msg, lang, emotion, history)
    history.append({"role": "user",      "content": msg})
    history.append({"role": "assistant", "content": response})
    session["chat_history"] = history[-(MAX_CHAT_HISTORY * 2):]
    session.modified = True
    return jsonify({"response": response, "emotion": emotion})


@app.route("/api/daily-status")
@login_required
def api_daily_status():
    uid = session["user_id"]
    return jsonify({
        "journals_today":  count_today_journals(uid),
        "checkins_today":  count_today_checkins(uid),
        "surveys_today":   count_today_surveys(uid),
        "journals_max":    MAX_JOURNALS_DAY,
        "checkins_max":    MAX_CHECKINS_DAY,
        "surveys_max":     MAX_SURVEYS_DAY,
    })


@app.route("/api/mood-trend")
@login_required
def api_mood_trend():
    uid = session["user_id"]
    h = get_student_risk_history(uid, days=14)
    data = [{"date": r["created_at"][:10], "score": r["risk_score"],
             "emotion": r["dominant_emotion"]}
            for r in h if r["risk_score"] is not None]
    return jsonify({"data": data, "count": len(data)})


@app.route("/api/location", methods=["POST"])
@login_required
def api_save_location():
    chk = verify_csrf()
    if chk: return chk
    if not rate_limit(f"location:{client_ip()}", 30, 60):
        return api_error("rate limited", 429)
    data, err = get_json_or_error()
    if err: return err
    try:
        lat = float(data.get("latitude", 0))
        lng = float(data.get("longitude", 0))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return api_error("invalid coords")
        city = clean_text(data.get("city", ""), 100) or None
        save_location(session["user_id"], lat, lng,
                      data.get("accuracy"), city)
        return api_ok(message="تم حفظ الموقع")
    except (ValueError, TypeError):
        return api_error("invalid coords")


@app.route("/api/game-score", methods=["POST"])
@login_required
def api_game_score():
    chk = verify_csrf()
    if chk: return chk
    data, err = get_json_or_error()
    if err: return err
    game = str(data.get("game", "")).strip()[:50]
    # Validate game name against allow-list
    ALLOWED_GAMES = {"breathing", "memory", "positive", "quiz", "emoji_match",
                     "star_catch", "gratitude", "color_mood", "reaction",
                     "affirmation"}
    if game not in ALLOWED_GAMES:
        return api_error("invalid game")
    try:
        score = max(0, min(99999, int(data.get("score", 0) or 0)))
        level = max(1, min(99, int(data.get("level", 1) or 1)))
        dur   = max(0, min(86400, int(data.get("duration", 0) or 0)))
    except (ValueError, TypeError):
        return api_error("invalid score")
    save_game_score(session["user_id"], game, score, level, dur)
    nb = check_and_award_achievements(session["user_id"])
    top = get_game_top_score(session["user_id"], game)
    return api_ok(top_score=top,
                  is_new_record=(score >= top and score > 0),
                  new_badges=len(nb))


@app.route("/api/breathing-done", methods=["POST"])
@login_required
def api_breathing_done():
    chk = verify_csrf()
    if chk: return chk
    data, err = get_json_or_error()
    if err: return err
    tech = str(data.get("technique", "4-7-8"))
    if tech not in ("4-7-8", "box", "calm"):
        tech = "4-7-8"
    try:
        cyc = max(0, min(200, int(data.get("cycles", 0) or 0)))
        dur = max(0, min(7200, int(data.get("duration", 0) or 0)))
    except (TypeError, ValueError):
        cyc = dur = 0
    if cyc < 1:
        return api_error("no cycles")
    mb = data.get("mood_before")
    ma = data.get("mood_after")
    try:
        mb = max(1, min(5, int(mb))) if mb is not None else None
    except (TypeError, ValueError):
        mb = None
    try:
        ma = max(1, min(5, int(ma))) if ma is not None else None
    except (TypeError, ValueError):
        ma = None
    save_breathing_session(session["user_id"], tech, cyc, dur, mb, ma)
    check_and_award_achievements(session["user_id"])
    return api_ok(message="جلسة التنفس محفوظة ✅")


@app.route("/api/streak")
@login_required
def api_streak():
    return jsonify(get_streak(session["user_id"]))


@app.route("/api/quick-stats")
@login_required
def api_quick_stats():
    return jsonify(get_student_personal_stats(session["user_id"]))


@app.route("/api/search-students")
@counselor_required
def api_search_students():
    import re as _re
    q = _re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s\-]", "",
                request.args.get("q", ""))[:50].strip().lower()
    sg = _supervised_grades()
    students = get_students_for_counselor(sg or None)
    if q:
        students = [s for s in students if
                    q in (s["anonymous_code"] or "").lower()
                    or q in (s["grade"] or "").lower()
                    or q in (s["display_name"] or "").lower()]
    return jsonify([dict(s) for s in students[:30]])


@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback():
    chk = verify_csrf()
    if chk: return chk
    if not rate_limit(f"feedback:{client_ip()}", 5, 300):
        return api_error("rate limited", 429)
    data, err = get_json_or_error()
    if err: return err
    fb = clean_text(data.get("feedback", ""), 500)
    if fb:
        summary = fb[:100].replace("\n", " ").replace("\r", " ")
        log.info("Feedback uid=%s len=%d summary=%s",
                 session.get("user_id"), len(fb), summary)
    return api_ok()


@app.route("/api/password-strength", methods=["POST"])
def api_password_strength():
    chk = verify_csrf()
    if chk: return chk
    if not rate_limit(f"ps:{client_ip()}", 30, 60):
        return api_error("rate limited", 429)
    data, err = get_json_or_error()
    if err: return err
    pw = str(data.get("password", ""))[:200]
    score, lbl_ar, lbl_en = password_strength_score(pw)
    return jsonify({
        "score": score,
        "label": lbl_ar if _lang() == "ar" else lbl_en,
        "max":   4,
    })


@app.route("/api/tips", methods=["GET", "POST"])
@login_required
def api_tips():
    if request.method == "POST":
        chk = verify_csrf()
        if chk: return chk
        if not rate_limit(f"tips:{client_ip()}", 5, 300):
            return api_error("rate limited", 429)
        data, err = get_json_or_error()
        if err: return err
        tip = clean_text(data.get("tip_ar", ""), 300)
        category = str(data.get("category", "general") or "general").strip().lower()[:30]
        ALLOWED = ("general", "stress", "study", "health", "social")
        if category not in ALLOWED:
            category = "general"
        if len(tip) < 10:
            return api_error("too short")
        submit_tip(session["user_id"], tip, "", category)
        return api_ok(message="submitted")
    return jsonify([dict(t) for t in get_approved_tips(20)])


@app.route("/api/statistics")
@login_required
def api_statistics():
    uid  = session["user_id"]
    role = session.get("role", "student")
    if role == "counselor":
        sg     = _supervised_grades()
        stats  = get_school_stats(sg or None)
        from database import get_db
        conn = get_db()
        rows = conn.execute(
            "SELECT DATE(created_at) as d, AVG(risk_score) as avg_r, "
            "COUNT(*) as cnt FROM emotion_analysis "
            "WHERE created_at >= datetime('now','-30 days') "
            "GROUP BY DATE(created_at) ORDER BY d ASC"
        ).fetchall()
        conn.close()
        trend = [{"date": r["d"], "avg_risk": round(r["avg_r"] or 0, 2),
                  "count": r["cnt"]} for r in rows]
        return jsonify({
            "stats":        dict(stats),
            "trend":        trend,
            "alert_counts": count_alerts_by_status(sg or None),
        })
    return jsonify(get_student_personal_stats(uid))


@app.route("/research")
@login_required
def research_dashboard():
    if session.get("role") != "counselor":
        return redirect(url_for("student_stats"))
    sg = _supervised_grades()
    stats = get_school_stats(sg or None)
    from database import get_db
    conn = get_db()
    emo_rows = conn.execute(
        "SELECT dominant_emotion, COUNT(*) as c FROM emotion_analysis "
        "GROUP BY dominant_emotion ORDER BY c DESC"
    ).fetchall()
    trend_rows = conn.execute(
        "SELECT DATE(created_at) as d, AVG(risk_score) as avg_r "
        "FROM emotion_analysis WHERE created_at >= datetime('now','-30 days') "
        "GROUP BY DATE(created_at) ORDER BY d"
    ).fetchall()
    acc_rows = conn.execute(
        "SELECT risk_level, COUNT(*) as c FROM emotion_analysis GROUP BY risk_level"
    ).fetchall()
    conn.close()
    emo_data   = [{"emotion": r["dominant_emotion"], "count": r["c"]}
                  for r in emo_rows]
    trend_data = [{"date": r["d"], "avg_risk": round(r["avg_r"] or 0, 2)}
                  for r in trend_rows]
    acc_data   = {r["risk_level"]: r["c"] for r in acc_rows}
    return render_template(
        "research.html",
        lang=_lang(), theme=_theme(),
        stats=stats,
        emo_data=json.dumps(emo_data),
        trend_data=json.dumps(trend_data),
        acc_data=json.dumps(acc_data),
    )


@app.route("/export-report")
@login_required
def export_report():
    uid  = session["user_id"]
    lang = _lang()
    stats    = get_student_personal_stats(uid)
    journals = get_student_journals(uid, limit=5)
    sk       = get_streak(uid)
    from datetime import datetime as _dt
    lines = []
    lines.append(f"SchoolMind AI — "
                 f"{'تقرير صحتي النفسية' if lang=='ar' else 'My Wellness Report'}")
    lines.append(f"{'التاريخ' if lang=='ar' else 'Date'}: {_dt.now():%Y-%m-%d}")
    lines.append("=" * 50)
    lines.append(f"{'الشعلة الحالية' if lang=='ar' else 'Current Streak'}: "
                 f"{sk['current']} {'يوم' if lang=='ar' else 'days'}")
    lines.append(f"{'إجمالي اليوميات' if lang=='ar' else 'Total Journals'}: "
                 f"{stats['total_journals']}")
    lines.append(f"{'متوسط درجة الخطر' if lang=='ar' else 'Avg Risk Score'}: "
                 f"{stats['avg_risk']}/10")
    lines.append(f"{'الإنجازات' if lang=='ar' else 'Achievements'}: "
                 f"{stats['achievements_count']}")
    lines.append("=" * 50)
    lines.append(f"{'آخر ٥ يوميات' if lang=='ar' else 'Last 5 Journals'}:")
    for j in journals:
        snippet = (j["content"] or "")[:60]
        lines.append(f"  - {(j['created_at'] or '')[:10]}: {snippet}...")
    content = "\n".join(lines)
    resp = make_response(content)
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="wellness_report_{_dt.now():%Y%m%d}.txt"'
    )
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp


# ─────────────────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────────────────
@app.errorhandler(400)
def e400(e):
    if request.is_json or request.path.startswith("/api/"):
        return api_error("Bad request", 400)
    flash("طلب غير صحيح", "error")
    return redirect(safe_referrer())


@app.errorhandler(403)
def e403(e):
    if request.is_json or request.path.startswith("/api/"):
        return api_error("Forbidden", 403)
    flash("انتهت صلاحية الجلسة", "error")
    return redirect(safe_referrer())


@app.errorhandler(404)
def e404(e):
    return render_template("404.html", lang=_lang(), theme=_theme()), 404


@app.errorhandler(413)
def e413(e):
    flash("الملف كبير جداً", "error")
    return redirect(safe_referrer())


@app.errorhandler(429)
def e429(e):
    if request.is_json or request.path.startswith("/api/"):
        return api_error("Rate limited", 429)
    flash("محاولات كثيرة", "error")
    return redirect(safe_referrer())


@app.errorhandler(500)
def e500(e):
    log.error("500: %s", e)
    if request.is_json or request.path.startswith("/api/"):
        return api_error("Server error", 500)
    try:
        flash("خطأ في الخادم", "error")
        return redirect(url_for("index"))
    except Exception:
        return "Internal Server Error", 500


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n  SchoolMind AI v21 · http://127.0.0.1:{port}  (debug={debug})\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
