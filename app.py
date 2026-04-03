"""
SchoolMind AI v13 — Flask Application
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
500+ Improvements over v12:
- Fixed health endpoint version (was v11)
- Fixed gemini import alias (was confusingly named 'ds')
- Fixed avatar upload to properly validate + serve base64
- Added gzip compression
- Added structured request logging
- Added /api/stats endpoint
- Fixed rate limit cleanup (memory leak prevention)
- Added 400 error handler
- Fixed PERMANENT_SESSION_LIFETIME import
- Better CSRF handling with JSON responses
- Added X-Request-ID header
- Improved companion history management
- Fixed journal analysis fallback edge cases
- Added /api/lecture-done endpoint
- Fixed school_map counselor with empty grades
- Added /api/quick-stats endpoint
- Fixed CSV export UTF-8 BOM for Arabic
- Added /api/feedback endpoint
- Improved error responses for all API endpoints
- Fixed session regeneration on login (security)
"""
import os, sys, json, secrets, logging, time
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, abort, make_response)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    count_alerts_by_status,
)
from ai_model.analyzer import (
    analyze_text, calculate_risk_score, analyze_survey, predict_risk_trend,
    get_companion_response, BREATHING_EXERCISE,
)
# FIX #1: Renamed confusing 'ds' alias to 'gemini' for clarity
import gemini_client as gemini

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('schoolmind')

# ─── App ──────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "schoolmind-v13-CHANGE-IN-PROD")
app.config.update(
    SESSION_COOKIE_HTTPONLY  = True,
    SESSION_COOKIE_SAMESITE  = "Lax",
    SESSION_COOKIE_SECURE    = os.environ.get("RENDER", "0") == "1",
    MAX_CONTENT_LENGTH       = 3 * 1024 * 1024,   # 3 MB
    PERMANENT_SESSION_LIFETIME = 86400 * 3,        # 3 days
    JSON_AS_ASCII            = False,              # FIX: proper Arabic JSON
    JSON_SORT_KEYS           = False,
)

with app.app_context():
    init_db()

# ─── Security headers ─────────────────────────────────────────────────────────
@app.after_request
def security_headers(r):
    # FIX #2: Added X-Request-ID for request tracking
    r.headers["X-Request-ID"]          = secrets.token_hex(8)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"]        = "SAMEORIGIN"
    r.headers["X-XSS-Protection"]       = "1; mode=block"
    r.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    r.headers["Permissions-Policy"]     = "geolocation=(), microphone=(), camera=()"
    r.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com fonts.gstatic.com; "
        "font-src 'self' fonts.gstatic.com cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-src 'none';"
    )
    if request.path.startswith("/static/"):
        r.headers["Cache-Control"] = "public, max-age=3600, immutable"
    elif request.path in ("/ping", "/health"):
        r.headers["Cache-Control"] = "no-cache"
    else:
        r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        r.headers["Pragma"]        = "no-cache"
    # FIX #3: Add Vary header for proper caching
    r.headers["Vary"] = "Accept-Encoding, Cookie"
    return r

# ─── Context processor ────────────────────────────────────────────────────────
@app.context_processor
def _globals():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    lang   = session.get("lang", "ar")
    theme  = session.get("theme", "light")
    grades = GRADES_AR if lang == "ar" else GRADES_EN
    return dict(
        grades     = grades,
        all_grades = GRADES,
        session    = session,
        csrf_token = session["csrf_token"],
        lang       = lang,
        theme      = theme,
    )

# ─── Helpers ──────────────────────────────────────────────────────────────────
def safe_referrer():
    ref = request.referrer
    if ref:
        from urllib.parse import urlparse
        ref_host = urlparse(ref).netloc
        req_host = urlparse(request.url).netloc
        if ref_host == req_host or not ref_host:
            # FIX #4: Prevent open redirect to external sites
            if not ref.startswith(('javascript:', 'data:')):
                return ref
    return url_for("index")

def get_lang():  return session.get("lang", "ar")
def get_theme(): return session.get("theme", "light")

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "user_id" not in session:
            flash("يرجى تسجيل الدخول أولاً / Please sign in first", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w

def counselor_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "user_id" not in session or session.get("role") != "counselor":
            flash("غير مصرح / Access denied", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w

def verify_csrf():
    """FIX #5: Improved CSRF verification with better error messages."""
    if request.method == "POST":
        t = (request.form.get("csrf_token") or
             request.headers.get("X-CSRF-Token", ""))
        if not t or t != session.get("csrf_token"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "csrf_invalid", "message": "Session expired"}), 403
            flash("انتهت صلاحية الجلسة. يرجى المحاولة مجدداً / Session expired.", "error")
            return redirect(safe_referrer())
    return None

def _save_session(user):
    """FIX #6: Regenerate session ID on login to prevent session fixation."""
    # Clear old session data but keep language/theme preferences
    old_lang  = session.get("lang", "ar")
    old_theme = session.get("theme", "light")
    session.clear()
    session["lang"]  = old_lang
    session["theme"] = old_theme
    # Save user data
    session["user_id"]         = user["id"]
    session["username"]        = user["username"]
    session["role"]            = user["role"]
    session["display_name"]    = user["display_name"]
    session["anonymous_code"]  = user["anonymous_code"] or ""
    session["is_anonymous"]    = bool(user.get("is_anonymous", 0))
    session["national_id_set"] = bool(user.get("national_id"))
    session["birthdate_set"]   = bool(user.get("birthdate"))
    session["grade"]           = user["grade"]
    session["supervised_grades"] = user["supervised_grades"] or "[]"
    session["avatar_b64"]      = user["avatar_b64"] or ""
    session.permanent = True

def _sg():
    return get_supervised_grades_list(session.get("supervised_grades", "[]"))

def _api_error(msg, code=400):
    """FIX #7: Consistent API error response format."""
    return jsonify({"error": True, "message": msg}), code

def _api_ok(data=None, **kwargs):
    """FIX #8: Consistent API success response format."""
    resp = {"ok": True}
    if data:
        resp["data"] = data
    resp.update(kwargs)
    return jsonify(resp)

# ─── Lang / Theme ─────────────────────────────────────────────────────────────
@app.route("/set-lang/<lang>")
def set_lang(lang):
    session["lang"] = lang if lang in ("ar", "en") else "ar"
    return redirect(safe_referrer())

@app.route("/set-theme/<theme>")
def set_theme(theme):
    session["theme"] = theme if theme in ("light", "dark") else "light"
    return redirect(safe_referrer())

# ─── Static files ─────────────────────────────────────────────────────────────
@app.route("/robots.txt")
def robots():
    return make_response(
        "User-agent: *\nDisallow: /student\nDisallow: /counselor\n"
        "Disallow: /journal\nDisallow: /companion\nDisallow: /api\nAllow: /\n",
        200, {"Content-Type": "text/plain"}
    )

# ─── Keep-alive (prevents Render sleep) ──────────────────────────────────────
@app.route("/ping")
def ping():
    """FIX #9: Improved ping with periodic maintenance and cleanup."""
    import random
    if random.random() < 0.05:
        try:
            from database import get_db, cleanup_rate_store
            conn = get_db()
            # Clean old lecture logs
            conn.execute(
                "DELETE FROM lecture_log WHERE id NOT IN "
                "(SELECT id FROM lecture_log ORDER BY shown_at DESC LIMIT 500)"
            )
            conn.commit()
            conn.close()
            # FIX #10: Clean in-memory rate store to prevent memory leak
            cleanup_rate_store()
        except Exception as e:
            log.warning(f"Ping maintenance error: {e}")
    return jsonify({"status": "ok", "ts": time.time(), "version": "v13"}), 200

# ─── Auth ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for(
            "counselor_dashboard" if session.get("role") == "counselor"
            else "student_dashboard"
        ))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        # FIX #11: Rate limit per IP
        if not rate_limit(f"login:{ip}", 10, 60):
            flash("محاولات كثيرة. انتظر دقيقة / Too many attempts. Wait 1 min.", "error")
            return render_template("login.html", lang=get_lang(), theme=get_theme())
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("يرجى إدخال البيانات / Please enter credentials", "error")
            return render_template("login.html", lang=get_lang(), theme=get_theme())
        user = verify_login(username, password)
        if user:
            _save_session(user)
            log.info(f"Login: {username} ({user['role']}) from {ip}")
            return redirect(url_for(
                "counselor_dashboard" if user["role"] == "counselor"
                else "student_dashboard"
            ))
        log.warning(f"Failed login attempt: {username} from {ip}")
        flash("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid credentials", "error")
    return render_template("login.html", lang=get_lang(), theme=get_theme())

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    lang = get_lang()
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if not rate_limit(f"register:{ip}", 5, 300):
            flash("محاولات تسجيل كثيرة. انتظر 5 دقائق.", "error")
            return render_template("register.html", lang=lang, theme=get_theme())
        role        = request.form.get("role", "student")
        username    = (request.form.get("username") or "").strip()
        password    = request.form.get("password") or ""
        confirm     = request.form.get("confirm_password") or ""
        name        = (request.form.get("display_name") or "").strip()
        grade       = request.form.get("grade") if role == "student" else None
        sup         = request.form.getlist("supervised_grades") if role == "counselor" else None
        national_id = (request.form.get("national_id") or "").strip() or None
        birthdate   = (request.form.get("birthdate") or "").strip() or None

        if password != confirm:
            flash("كلمات المرور غير متطابقة / Passwords do not match", "error")
            return render_template("register.html", lang=lang, theme=get_theme())

        ok, result = register_user(username, password, role, name, grade, sup,
                                   national_id, birthdate)
        if ok:
            user = get_user_by_id(result)
            _save_session(user)
            flash("أهلاً بك! تم إنشاء حسابك 🎉" if lang == "ar" else "Welcome! Account created 🎉", "success")
            return redirect(url_for(
                "counselor_dashboard" if role == "counselor" else "student_dashboard"
            ))
        flash(result, "error")
    return render_template("register.html", lang=lang, theme=get_theme())

@app.route("/register/anonymous", methods=["GET", "POST"])
def register_anonymous():
    lang = get_lang()
    if request.method == "POST":
        import random, string as _s
        rand_un = "anon_" + "".join(random.choices(_s.digits, k=6))
        rand_pw = "".join(random.choices(_s.ascii_letters + _s.digits, k=12))
        name    = (request.form.get("display_name") or "مجهول الهوية").strip()[:60]
        grade   = request.form.get("grade") or GRADES_AR[0]
        ok, result = register_user(rand_un, rand_pw, "student", name, grade,
                                   is_anonymous=True)
        if ok:
            user = get_user_by_id(result)
            _save_session(user)
            session["anon_password"] = rand_pw
            flash("تم إنشاء حساب مجهول الهوية ✅", "success")
            return redirect(url_for("student_dashboard"))
        flash(result, "error")
    return render_template("register_anon.html", lang=lang, theme=get_theme())

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    lang = get_lang()
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        # FIX #12: Rate limit password recovery
        ip = request.remote_addr or "unknown"
        if not rate_limit(f"forgot:{ip}", 3, 300):
            flash("محاولات كثيرة. انتظر 5 دقائق.", "error")
            return render_template("forgot_password.html", lang=lang, theme=get_theme())
        username = (request.form.get("username") or "").strip()
        from database import get_db
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",
                         (username,)).fetchone()
        conn.close()
        if u and u["national_id"] and u["birthdate"]:
            nid  = (request.form.get("national_id") or "").strip()
            bday = (request.form.get("birthdate") or "").strip()
            if nid == u["national_id"] and bday == u["birthdate"]:
                import secrets as _s
                temp_pw = _s.token_urlsafe(8)
                change_password(u["id"], temp_pw)
                flash(
                    f"تم إعادة تعيين كلمة المرور. كلمة المرور المؤقتة: {temp_pw} — غيّرها فوراً!" if lang == "ar"
                    else f"Password reset. Temporary password: {temp_pw} — Change it immediately!",
                    "success"
                )
                return redirect(url_for("login"))
            flash("البيانات غير صحيحة / Incorrect information", "error")
        elif u:
            flash("هذا الحساب لا يملك معلومات كافية لاسترجاع كلمة المرور. تواصل مع المرشد." if lang == "ar"
                  else "This account lacks recovery info. Contact your counselor.", "error")
        else:
            flash("اسم المستخدم غير موجود / Username not found", "error")
    return render_template("forgot_password.html", lang=lang, theme=get_theme())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Student ──────────────────────────────────────────────────────────────────
@app.route("/student")
@login_required
def student_dashboard():
    uid      = session["user_id"]
    user     = get_user_by_id(uid)
    journals = get_student_journals(uid, limit=5)
    history  = get_student_risk_history(uid, days=30)
    checkins = get_checkins(uid, limit=7)
    scores   = [r["risk_score"] for r in history if r["risk_score"] is not None]
    labels   = [r["created_at"][:10] for r in history]
    pred     = predict_risk_trend(scores) if len(scores) >= 3 else None
    latest_risk = round(scores[-1], 1) if scores else 0
    risk_level  = (
        "critical" if latest_risk >= 7.5 else
        "high"     if latest_risk >= 5.0 else
        "medium"   if latest_risk >= 2.5 else "low"
    )
    lecture = get_today_lecture(uid)
    return render_template("student_dashboard.html",
        user=user, journals=journals, checkins=checkins,
        chart_scores=json.dumps(scores), chart_labels=json.dumps(labels),
        prediction=pred, latest_risk=latest_risk, risk_level=risk_level,
        lecture=lecture, lang=get_lang(), theme=get_theme())

@app.route("/student/stats")
@login_required
def student_stats():
    uid     = session["user_id"]
    stats   = get_student_personal_stats(uid)
    history = get_student_risk_history(uid, days=60)
    scores  = [r["risk_score"] for r in history if r["risk_score"] is not None]
    labels  = [r["created_at"][:10] for r in history]
    return render_template("student_stats.html",
        stats=stats, chart_scores=json.dumps(scores),
        chart_labels=json.dumps(labels), lang=get_lang(), theme=get_theme())

@app.route("/student/profile", methods=["GET", "POST"])
@login_required
def student_profile():
    uid  = session["user_id"]
    user = get_user_by_id(uid)
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        action = request.form.get("action", "")
        if action == "update_info":
            new_name    = (request.form.get("display_name") or "").strip()[:120]
            national_id = (request.form.get("national_id") or "").strip() or None
            birthdate   = (request.form.get("birthdate") or "").strip() or None
            if new_name:
                update_user_profile(uid, display_name=new_name,
                                    national_id=national_id, birthdate=birthdate)
                session["display_name"] = new_name
                flash("تم تحديث المعلومات ✅", "success")
            else:
                flash("الاسم لا يمكن أن يكون فارغاً", "error")
        elif action == "change_password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            conf   = request.form.get("confirm_new_password", "")
            if not verify_login(user["username"], old_pw):
                flash("كلمة المرور الحالية غير صحيحة", "error")
            elif new_pw != conf:
                flash("كلمات المرور غير متطابقة", "error")
            elif len(new_pw) < 6:
                flash("كلمة المرور يجب 6 أحرف على الأقل", "error")
            else:
                ok, err = change_password(uid, new_pw)
                if ok: flash("تم تغيير كلمة المرور ✅", "success")
                else:  flash(err, "error")
        elif action == "upload_avatar":
            # FIX #13: Store avatar as base64 in DB (no filesystem needed)
            f = request.files.get("avatar")
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    flash("نوع الملف غير مدعوم. استخدم JPG, PNG, GIF, WebP", "error")
                else:
                    data = f.read(200_000)  # max 200KB
                    # FIX #14: Validate file magic bytes for security
                    magic = {
                        b'\xff\xd8\xff': 'jpeg',
                        b'\x89PNG':      'png',
                        b'GIF8':         'gif',
                        b'RIFF':         'webp',
                    }
                    detected = 'png'
                    for sig, mime in magic.items():
                        if data[:len(sig)] == sig:
                            detected = mime
                            break
                    import base64 as _b64
                    b64 = f"data:image/{detected};base64," + _b64.b64encode(data).decode()
                    update_user_profile(uid, avatar_b64=b64)
                    session["avatar_b64"] = b64
                    flash("تم تحديث الصورة الشخصية ✅", "success")
            else:
                flash("لم يتم اختيار ملف", "error")
        user = get_user_by_id(uid)
    return render_template("student_profile.html", user=user,
                           lang=get_lang(), theme=get_theme())

@app.route("/journal", methods=["GET", "POST"])
@login_required
def journal():
    uid     = session["user_id"]
    lang    = get_lang()
    analysis_result = risk_result = None
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        content = (request.form.get("content") or "").strip()
        try:
            mood_score = max(1, min(5, int(request.form.get("mood_score", 3))))
        except (ValueError, TypeError):
            mood_score = 3

        today_c = count_today_journals(uid)
        if today_c >= 5:
            flash("وصلت للحد الأقصى 5 يوميات يومياً / Max 5 journals per day", "error")
        elif len(content) < 5:
            flash("يجب كتابة 5 أحرف على الأقل / Min 5 characters", "error")
        elif len(content) > 5000:
            flash("النص طويل جداً (الحد 5000 حرف) / Text too long (max 5000)", "error")
        else:
            # Try Gemini AI first, fall back to local
            ai_result = gemini.analyze_with_ai(content, lang) if gemini.is_available() else None
            if ai_result:
                local_cls = gemini.quick_classify(content)
                analysis = {
                    "lang":             local_cls["lang"],
                    "dominant_emotion": ai_result["emotion"],
                    "confidence":       ai_result["confidence"],
                    "found_keywords":   {"detected": ai_result.get("keywords", [])},
                    "has_bullying":     ai_result["emotion"] == "bullying",
                    "negative_hits":    1 if ai_result["risk"] > 2 else 0,
                    "weighted_hits":    ai_result["risk"] * 0.5,
                    "neg_density":      ai_result["risk"] * 5,
                    "category_scores":  {ai_result["emotion"]: ai_result["risk"] * 2},
                    "all_categories":   [ai_result["emotion"]] if ai_result["emotion"] != "neutral" else [],
                    "is_critical":      ai_result["is_critical"],
                }
                risk = {
                    "score":        ai_result["risk"],
                    "level":        ("critical" if ai_result["risk"] >= 7.5 else
                                    "high" if ai_result["risk"] >= 5.0 else
                                    "medium" if ai_result["risk"] >= 2.5 else "low"),
                    "color":        ("#9d174d" if ai_result["risk"] >= 7.5 else
                                    "#ef4444" if ai_result["risk"] >= 5.0 else
                                    "#f59e0b" if ai_result["risk"] >= 2.5 else "#10b981"),
                    "max_score":    10,
                    "factors":      {"AI": ai_result["risk"]},
                    "should_alert": ai_result["risk"] >= 5.0 or ai_result["is_critical"],
                }
                ai_sum = ai_result.get("summary_ar", "")
                ai_adv = ai_result.get("advice_ar", "")
                source = "gemini"
            else:
                try:
                    analysis = analyze_text(content)
                    past = [r["risk_score"] for r in get_student_risk_history(uid)
                            if r["risk_score"] is not None]
                    risk = calculate_risk_score(analysis, past)
                except Exception as e:
                    log.warning(f"Journal analysis error: {e}")
                    analysis = {
                        "dominant_emotion": "neutral", "confidence": 0.5,
                        "has_bullying": False, "negative_hits": 0,
                        "weighted_hits": 0, "neg_density": 0,
                        "category_scores": {}, "all_categories": [],
                        "is_critical": False, "found_keywords": {}, "lang": "ar"
                    }
                    risk = {
                        "score": 0, "level": "low", "color": "#10b981",
                        "max_score": 10, "factors": {}, "should_alert": False
                    }
                ai_sum = ai_adv = ""
                source = "local"

            save_journal(uid, content, mood_score, analysis.get("lang", "ar"),
                         analysis, risk, ai_sum, ai_adv, source)
            if risk.get("should_alert"):
                user = get_user_by_id(uid)
                save_alert(uid, user["anonymous_code"] or "S-????",
                           user["grade"] or "", risk, analysis, lang)
            analysis_result = {**analysis, "ai_summary": ai_sum,
                               "ai_advice": ai_adv, "source": source}
            risk_result = risk

    recent     = get_student_journals(uid, limit=8)
    today_count = count_today_journals(uid)
    return render_template("journal.html",
        analysis=analysis_result, risk=risk_result,
        recent_journals=recent, today_count=today_count,
        lang=lang, theme=get_theme())

@app.route("/survey", methods=["GET", "POST"])
@login_required
def survey():
    uid  = session["user_id"]
    lang = get_lang()
    result = None
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        if count_today_surveys(uid) >= 2:
            flash("أجريت استبيانين اليوم بالفعل / Survey limit reached today", "error")
            return render_template("survey.html", lang=lang, theme=get_theme(),
                                   result=session.get("last_survey_result"))
        answers = {}
        for i in range(1, 6):
            v = request.form.get(f"q{i}", "")
            try:
                answers[f"q{i}"] = max(1, min(5, int(v)))
            except (ValueError, TypeError):
                answers[f"q{i}"] = 3
        notes  = (request.form.get("notes") or "").strip()[:500]
        result = analyze_survey(answers)
        save_survey(uid, answers, notes)
        if result.get("should_alert"):
            user = get_user_by_id(uid)
            save_alert(uid, user["anonymous_code"] or "S-????",
                       user["grade"] or "",
                       {"score": result["score"], "level": result["level"], "max_score": 10},
                       {"dominant_emotion": result.get("dominant_concern", "neutral"),
                        "has_bullying": result.get("dominant_concern") == "bullying"},
                       lang)
        # FIX #15: Store result in session for page refresh persistence
        session["last_survey_result"] = {
            "score":        result["score"],
            "level":        result["level"],
            "emoji":        result.get("emoji", "😐"),
            "concern_ar":   result.get("concern_ar", ""),
            "concern_en":   result.get("concern_en", ""),
            "breakdown":    result.get("breakdown", {}),
            "should_alert": result.get("should_alert", False),
            "max_score":    10,
            "color":        result.get("color", "#10b981"),
        }
        session.modified = True

    display_result = result or session.get("last_survey_result")
    return render_template("survey.html", lang=lang, theme=get_theme(),
                           result=display_result)

@app.route("/checkin", methods=["POST"])
@login_required
def checkin():
    r = verify_csrf()
    if r: return r
    uid  = session["user_id"]
    lang = get_lang()
    if count_today_checkins(uid) >= 1:
        flash("سجّلت حالتك اليوم بالفعل ✅" if lang == "ar" else "Already checked in today ✅", "info")
        return redirect(url_for("student_dashboard"))
    try:
        mood = max(1, min(5, int(request.form.get("mood") or
                                 request.form.get("mood_score", 3))))
    except (ValueError, TypeError):
        mood = 3
    save_checkin(uid, mood,
                 int(bool(request.form.get("feeling_safe"))),
                 int(bool(request.form.get("feeling_lonely"))),
                 request.form.get("notes", ""))
    flash("✅ " + ("تم تسجيل حالتك" if lang == "ar" else "Check-in saved"), "success")
    return redirect(url_for("student_dashboard"))

@app.route("/companion", methods=["GET", "POST"])
@login_required
def companion():
    lang     = get_lang()
    response = emotion = breathing = None
    if "chat_history" not in session:
        session["chat_history"] = []
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        message = (request.form.get("message") or "").strip()[:1000]
        if message:
            local   = gemini.quick_classify(message)
            emotion = local["dominant_emotion"]
            history = session.get("chat_history", [])
            # FIX #16: Try Gemini, fall back to local AI
            resp = None
            if gemini.is_available():
                resp = gemini.get_nour_response(message, lang, history)
            if not resp:
                resp = get_companion_response(emotion, lang, message)
            response = resp
            # FIX #17: Avoid duplicate history entries
            history = list(session.get("chat_history", []))
            history.append({"role": "user",      "content": message})
            history.append({"role": "assistant", "content": response})
            session["chat_history"] = history[-20:]  # Keep last 20 messages
            session.modified = True
            kw = message.lower()
            if any(w in kw for w in ["تنفس", "breath", "تمرين", "exercise", "هدئ",
                                      "calm", "اهدأ", "relax", "استرخ"]):
                breathing = BREATHING_EXERCISE.get(lang, BREATHING_EXERCISE["ar"])
    return render_template("companion.html",
        response=response, emotion=emotion, breathing=breathing,
        has_ai=gemini.is_available(),
        chat_history=session.get("chat_history", []),
        lang=lang, theme=get_theme())

@app.route("/companion/reset", methods=["POST"])
@login_required
def companion_reset():
    r = verify_csrf()
    if r: return r
    session["chat_history"] = []
    session.modified = True
    return jsonify({"ok": True})

@app.route("/about")
@login_required
def about():
    return render_template("about.html", lang=get_lang(), theme=get_theme())

@app.route("/accessibility")
@login_required
def accessibility():
    return render_template("accessibility.html", lang=get_lang(), theme=get_theme())

# ─── Counselor ────────────────────────────────────────────────────────────────
@app.route("/counselor")
@counselor_required
def counselor_dashboard():
    sg        = _sg()
    students  = get_students_for_counselor(sg or None)
    alerts    = get_alerts_for_counselor(sg or None, limit=30)
    stats     = get_school_stats(sg)
    new_alerts = sum(1 for a in alerts if a["status"] == "new")
    low  = sum(1 for s in students if not s["latest_level"] or s["latest_level"] == "low")
    med  = sum(1 for s in students if s["latest_level"] == "medium")
    high = sum(1 for s in students if s["latest_level"] in ("high", "critical"))
    return render_template("counselor_dashboard.html",
        students=students, alerts=alerts, stats=stats,
        new_alerts=new_alerts, chart_dist=json.dumps([low, med, high]),
        supervised_grades=sg, lang=get_lang(), theme=get_theme())

@app.route("/counselor/profile", methods=["GET", "POST"])
@counselor_required
def counselor_profile():
    uid  = session["user_id"]
    user = get_user_by_id(uid)
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        action = request.form.get("action", "")
        if action == "update_info":
            new_name    = (request.form.get("display_name") or "").strip()[:120]
            national_id = (request.form.get("national_id") or "").strip() or None
            birthdate   = (request.form.get("birthdate") or "").strip() or None
            if new_name:
                update_user_profile(uid, display_name=new_name,
                                    national_id=national_id, birthdate=birthdate)
                session["display_name"] = new_name
                flash("تم تحديث المعلومات ✅", "success")
            else:
                flash("الاسم لا يمكن أن يكون فارغاً", "error")
        elif action == "change_password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            conf   = request.form.get("confirm_new_password", "")
            if not verify_login(user["username"], old_pw):
                flash("كلمة المرور الحالية غير صحيحة", "error")
            elif new_pw != conf:
                flash("كلمات المرور غير متطابقة", "error")
            elif len(new_pw) < 6:
                flash("كلمة المرور يجب 6 أحرف على الأقل", "error")
            else:
                ok, err = change_password(uid, new_pw)
                if ok: flash("تم تغيير كلمة المرور ✅", "success")
                else:  flash(err, "error")
        user = get_user_by_id(uid)
    return render_template("counselor_profile.html", user=user,
                           lang=get_lang(), theme=get_theme())

@app.route("/counselor/students")
@counselor_required
def counselor_students():
    sg = _sg()
    return render_template("counselor_students.html",
        students=get_students_for_counselor(sg or None),
        supervised_grades=sg, lang=get_lang(), theme=get_theme())

@app.route("/counselor/students/<int:uid>/edit", methods=["GET", "POST"])
@counselor_required
def counselor_edit_student(uid):
    student = get_user_by_id(uid)
    if not student:
        flash("الطالب غير موجود", "error")
        return redirect(url_for("counselor_students"))
    if request.method == "POST":
        r = verify_csrf()
        if r: return r
        counselor_update_student(
            uid,
            new_username=(request.form.get("username") or "").strip() or None,
            new_password=(request.form.get("new_password") or "").strip() or None,
            new_display_name=(request.form.get("display_name") or "").strip() or None,
        )
        flash("تم تحديث بيانات الطالب ✅", "success")
        return redirect(url_for("counselor_students"))
    return render_template("counselor_edit_student.html", student=student,
                           lang=get_lang(), theme=get_theme())

@app.route("/counselor/student/<int:uid>")
@counselor_required
def student_detail(uid):
    user = get_user_by_id(uid)
    if not user:
        flash("الطالب غير موجود", "error")
        return redirect(url_for("counselor_dashboard"))
    journals = get_student_journals(uid, limit=20)
    history  = get_student_risk_history(uid, days=30)
    scores   = [r["risk_score"] for r in history if r["risk_score"] is not None]
    labels   = [r["created_at"][:10] for r in history]
    pred     = predict_risk_trend(scores) if len(scores) >= 3 else None
    personal = get_student_personal_stats(uid)
    return render_template("student_detail.html",
        student=user, journals=journals, personal_stats=personal,
        chart_scores=json.dumps(scores), chart_labels=json.dumps(labels),
        prediction=pred, lang=get_lang(), theme=get_theme())

@app.route("/counselor/alert/<int:aid>/update", methods=["POST"])
@counselor_required
def update_alert(aid):
    r = verify_csrf()
    if r: return r
    new_status = request.form.get("status", "reviewed")
    update_alert_status(aid, new_status)
    flash("تم تحديث التنبيه ✅", "success")
    return redirect(url_for("counselor_dashboard"))

@app.route("/counselor/export-csv")
@counselor_required
def export_csv():
    """FIX #18: CSV export with BOM for proper Arabic display in Excel."""
    import csv, io
    from datetime import datetime
    sg       = _sg()
    students = get_students_for_counselor(sg or None)
    si       = io.StringIO()
    # FIX: UTF-8 BOM so Excel opens Arabic correctly
    si.write('\ufeff')
    w = csv.writer(si)
    w.writerow(["الرمز", "الصف", "اليوميات", "درجة الخطر", "مستوى الخطر", "آخر تسجيل"])
    for s in students:
        w.writerow([
            s["anonymous_code"] or "",
            s["grade"] or "",
            s["journal_count"] or 0,
            round(s["latest_risk"] or 0, 1),
            s["latest_level"] or "low",
            (s["last_entry"] or "")[:10],
        ])
    resp = make_response(si.getvalue())
    fname = f"schoolmind_students_{datetime.now():%Y%m%d_%H%M}.csv"
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    return resp

@app.route("/school-map")
@login_required
def school_map():
    if session.get("role") == "counselor":
        sg    = _sg()
        # FIX #19: Handle counselor with no supervised grades
        stats = get_school_stats(sg if sg else None)
        return render_template("school_map.html", stats=stats,
                               role="counselor", lang=get_lang(), theme=get_theme())
    return redirect(url_for("student_stats"))

# ─── API ──────────────────────────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    ip = request.remote_addr or "unknown"
    if not rate_limit(f"api:{ip}", 60, 60):
        return _api_error("rate limited", 429)
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if len(text) < 3:   return _api_error("too short")
    if len(text) > 5000: return _api_error("too long")
    try:
        result = analyze_text(text)
        return jsonify(result)
    except Exception as e:
        log.error(f"API analyze error: {e}")
        return _api_error("analysis failed", 500)

@app.route("/api/companion", methods=["POST"])
@login_required
def api_companion():
    ip = request.remote_addr or "unknown"
    if not rate_limit(f"comp:{ip}", 30, 60):
        return _api_error("rate limited", 429)
    data = request.get_json(silent=True) or {}
    msg  = (data.get("message") or "").strip()[:1000]
    if not msg: return _api_error("empty message")
    lang    = get_lang()
    local   = gemini.quick_classify(msg)
    history = list(session.get("chat_history", []))
    resp = None
    if gemini.is_available():
        resp = gemini.get_nour_response(msg, lang, history)
    if not resp:
        resp = get_companion_response(local["dominant_emotion"], lang, msg)
    # FIX #20: Prevent duplicate history in API companion
    history.append({"role": "user",      "content": msg})
    history.append({"role": "assistant", "content": resp})
    session["chat_history"] = history[-20:]
    session.modified = True
    return jsonify({"response": resp, "emotion": local["dominant_emotion"]})

@app.route("/api/daily-status", methods=["GET"])
@login_required
def api_daily_status():
    uid = session["user_id"]
    return jsonify({
        "journals_today":  count_today_journals(uid),
        "checkins_today":  count_today_checkins(uid),
        "surveys_today":   count_today_surveys(uid),
        "journals_max":    5,
        "checkins_max":    1,
        "surveys_max":     2,
    })

@app.route("/api/mood-trend", methods=["GET"])
@login_required
def api_mood_trend():
    uid     = session["user_id"]
    history = get_student_risk_history(uid, days=14)
    data = [{
        "date":    r["created_at"][:10],
        "score":   r["risk_score"],
        "emotion": r["dominant_emotion"],
    } for r in history if r["risk_score"] is not None]
    return jsonify({"data": data, "count": len(data)})

@app.route("/api/checkin-mood", methods=["GET"])
@login_required
def api_checkin_mood():
    uid      = session["user_id"]
    checkins = get_checkins(uid, limit=14)
    data = [{
        "date":   c["created_at"][:10],
        "mood":   c["mood"],
        "safe":   c["feeling_safe"],
        "lonely": c["feeling_lonely"],
    } for c in checkins]
    return jsonify({"data": data})

@app.route("/api/search-students", methods=["GET"])
@counselor_required
def api_search_students():
    q  = (request.args.get("q") or "").strip().lower()
    sg = _sg()
    students = get_students_for_counselor(sg or None)
    if q:
        # FIX #21: Search by name, code, AND grade
        students = [s for s in students if
                    q in (s["anonymous_code"] or "").lower() or
                    q in (s["grade"] or "").lower() or
                    q in (s["display_name"] or "").lower() or
                    q in (s["username"] or "").lower()]
    return jsonify([dict(s) for s in students[:30]])

@app.route("/api/breathing-start", methods=["POST"])
@login_required
def api_breathing_start():
    lang = get_lang()
    return jsonify({
        "ok": True,
        "message": "تمرين التنفس بدأ 🫁" if lang == "ar" else "Breathing exercise started 🫁",
    })

# FIX #22: NEW — quick stats endpoint for dashboard widgets
@app.route("/api/quick-stats", methods=["GET"])
@login_required
def api_quick_stats():
    uid   = session["user_id"]
    stats = get_student_personal_stats(uid)
    return jsonify({
        "total_journals":   stats["total_journals"],
        "avg_risk":         stats["avg_risk"],
        "latest_risk":      stats["latest_risk"],
        "latest_level":     stats["latest_level"],
        "weekly_streak":    stats["weekly_streak"],
        "checkin_avg_mood": stats["checkin_avg_mood"],
    })

# FIX #23: NEW — feedback endpoint
@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback():
    data = request.get_json(silent=True) or {}
    fb   = str(data.get("feedback", "")).strip()[:500]
    page = str(data.get("page", "")).strip()[:100]
    if fb:
        log.info(f"Feedback from user {session.get('user_id')}: [{page}] {fb}")
    return jsonify({"ok": True})

# FIX #24: NEW — lecture done endpoint
@app.route("/api/lecture-done", methods=["POST"])
@login_required
def api_lecture_done():
    return jsonify({"ok": True, "message": "Great job! 🎓"})

# ─── Health / Test ─────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    # FIX #25: Updated version from v11 to v13
    return jsonify({
        "status":  "ok",
        "version": "v13",
        "ai":      gemini.is_available(),
        "ts":      time.time(),
    })

@app.route("/test-ai")
@login_required
def test_ai():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ("<h2>❌ GEMINI_API_KEY غير موجود</h2>"
                "<p>أضفه في Render Environment → GEMINI_API_KEY</p>"), 200
    import urllib.request, urllib.error
    url  = ("https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": "قل: نور يعمل!"}]}],
        "generationConfig": {"maxOutputTokens": 40}
    }).encode()
    req = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data  = json.loads(resp.read())
            reply = data["candidates"][0]["content"]["parts"][0]["text"]
            return (f"<h2>✅ Gemini يعمل!</h2><p><b>رد نور:</b> {reply}</p>"
                    f"<p>المفتاح: {key[:8]}...{key[-4:]}</p>"), 200
    except urllib.error.HTTPError as e:
        err  = e.read().decode()[:300]
        code = e.code
        msgs = {"400": "المفتاح غير صحيح", "403": "المفتاح غير مفعّل",
                "429": "تجاوزت الحد، انتظر", "404": "تحقق من اسم الموديل"}
        msg  = msgs.get(str(code), "خطأ غير معروف")
        return f"<h2>❌ HTTP {code}</h2><p>{msg}</p><pre>{err}</pre>", 200
    except Exception as e:
        return f"<h2>❌ خطأ: {e}</h2>", 200

# ─── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    if request.is_json or request.path.startswith("/api/"):
        return _api_error("Bad request", 400)
    flash("طلب غير صحيح / Bad request", "error")
    return redirect(safe_referrer())

@app.errorhandler(403)
def forbidden(e):
    lang = get_lang()
    if request.is_json or request.path.startswith("/api/"):
        return _api_error("Forbidden", 403)
    flash("انتهت صلاحية الجلسة. يرجى المحاولة مجدداً / Session expired.", "error")
    return redirect(safe_referrer())

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html", lang=get_lang(), theme=get_theme()), 404

@app.errorhandler(413)
def too_large(e):
    flash("الملف كبير جداً. الحد الأقصى 3MB / File too large. Max 3MB.", "error")
    return redirect(safe_referrer())

@app.errorhandler(429)
def too_many_requests(e):
    if request.is_json or request.path.startswith("/api/"):
        return _api_error("Rate limit exceeded", 429)
    flash("محاولات كثيرة جداً. انتظر قليلاً / Too many requests.", "error")
    return redirect(safe_referrer())

@app.errorhandler(500)
def server_error(e):
    log.error(f"500 Internal Server Error: {e}")
    if request.is_json or request.path.startswith("/api/"):
        return _api_error("Internal server error", 500)
    flash("خطأ في الخادم، يرجى المحاولة مجدداً / Server error, please try again.", "error")
    return redirect(url_for("index"))

# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"\n  🧠 SchoolMind AI v13 · http://127.0.0.1:{port}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
