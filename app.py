"""SchoolMind AI v19 — 200+ improvements over v16"""
import os, sys, json, re, secrets, logging, time, hashlib
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, abort, make_response, Response)

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
    count_alerts_by_status, cleanup_rate_store,
    save_location, get_student_location, get_all_student_locations,
    save_goal, get_goals, update_goal, delete_goal,
    save_game_score, get_game_scores, get_game_top_score,
    save_breathing_session, get_breathing_stats,
    get_streak, update_streak, get_achievements, award_achievement,
    check_and_award_achievements, BADGES,
    get_user_by_username, get_approved_tips, submit_tip,
    log_counselor_action, sanitize_grades, password_strength_score,
)
from ai_model.analyzer import (
    analyze_text, calculate_risk_score, analyze_survey, predict_risk_trend,
    get_companion_response, BREATHING_EXERCISE,
)
import gemini_client as gemini

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('schoolmind')

# Constants
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY   = True,
    SESSION_COOKIE_SAMESITE   = "Lax",
    SESSION_COOKIE_SECURE     = os.environ.get("RENDER", "0") == "1",
    SESSION_COOKIE_NAME       = "_sm_s",
    MAX_CONTENT_LENGTH        = 5 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME= 86400 * SESSION_DAYS,
    JSON_AS_ASCII             = False,
    JSONIFY_PRETTYPRINT_REGULAR = False,
)

try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass

with app.app_context():
    init_db()

# Gemini availability cache
_gc = {"ok": None, "ts": 0}
def _gok():
    now = time.time()
    if now - _gc["ts"] > 60:
        _gc["ok"] = gemini.is_available()
        _gc["ts"] = now
    return _gc["ok"]

@app.after_request
def sec(r):
    r.headers["X-Request-ID"]           = secrets.token_hex(8)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"]        = "SAMEORIGIN"
    r.headers["X-XSS-Protection"]       = "1; mode=block"
    r.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    r.headers["Permissions-Policy"]     = "geolocation=(self), camera=(), microphone=()"
    r.headers["Content-Security-Policy"]= (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com fonts.gstatic.com unpkg.com; "
        "font-src 'self' fonts.gstatic.com cdn.jsdelivr.net; "
        "img-src 'self' data: blob: *.tile.openstreetmap.org; "
        "connect-src 'self' nominatim.openstreetmap.org; frame-src 'none';"
    )
    if os.environ.get("RENDER") == "1":
        r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.path.startswith("/static/"):
        r.headers["Cache-Control"] = "public, max-age=604800"
    elif request.path not in ("/ping", "/health"):
        r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return r

@app.context_processor
def _ctx():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    lang  = session.get("lang", "ar")
    theme = session.get("theme", "light")
    hour  = datetime.now().hour
    greet = ("صباح الخير" if 5<=hour<12 else "مساء الخير" if 12<=hour<18 else "مساء النور") if lang=="ar" else ("Good Morning" if 5<=hour<12 else "Good Afternoon" if 12<=hour<18 else "Good Evening")
    unread = session.get("new_badges_count", 0)
    QUOTES_AR = ["كل يوم تكتب فيه هو انتصار 🌟","مشاعرك تستحق أن تُسمع 💙","أنت أقوى مما تعتقد 💪","خطوة صغيرة كل يوم = فارق كبير 🚀","الاهتمام بصحتك النفسية أذكى شيء تفعله 🧠","لا بأس بأن تطلب المساعدة 🤝","أنت لست وحدك في هذا 💜","الأيام الصعبة تنتهي دائماً ☀️"]
    QUOTES_EN = ["Every day you write is a victory 🌟","Your feelings deserve to be heard 💙","You are stronger than you think 💪","One small step daily = a big difference 🚀","Mental health care is the smartest thing 🧠","It's okay to ask for help 🤝","You are not alone 💜","Hard days always end ☀️"]
    from datetime import date as _d
    q = QUOTES_AR[_d.today().toordinal() % len(QUOTES_AR)] if lang=="ar" else QUOTES_EN[_d.today().toordinal() % len(QUOTES_EN)]
    return dict(grades=GRADES_AR if lang=="ar" else GRADES_EN, all_grades=GRADES,
                session=session, csrf_token=session["csrf_token"],
                lang=lang, theme=theme, greeting=greet,
                unread_badges=unread, daily_quote=q)

def _lang():  return session.get("lang", "ar")
def _theme(): return session.get("theme", "light")

def _sfp():
    ua = request.headers.get("User-Agent","")[:80]
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()
    return hashlib.sha256(f"{ip}:{ua[:40]}".encode()).hexdigest()[:16]

def safe_ref():
    ref = request.referrer or ""
    try:
        from urllib.parse import urlparse
        p = urlparse(ref); h = urlparse(request.url).netloc
        if p.netloc in ("", h) and not ref.startswith(("javascript:", "data:")):
            return ref
    except: pass
    return url_for("index")

def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if "user_id" not in session:
            flash("يرجى تسجيل الدخول" if _lang()=="ar" else "Please log in", "error")
            return redirect(url_for("login"))
        if session.get("_fp") and session["_fp"] != _sfp():
            session.clear()
            flash("انتهت الجلسة لأسباب أمنية" if _lang()=="ar" else "Session expired", "error")
            return redirect(url_for("login"))
        return f(*a,**kw)
    return w

def counselor_required(f):
    @wraps(f)
    def w(*a,**kw):
        if "user_id" not in session or session.get("role") != "counselor":
            flash("غير مصرح" if _lang()=="ar" else "Access denied","error")
            return redirect(url_for("login"))
        return f(*a,**kw)
    return w

def verify_csrf():
    if request.method == "POST":
        tok = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token","")
        if not tok or tok != session.get("csrf_token"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error":"csrf_invalid"}), 403
            flash("انتهت صلاحية الجلسة" if _lang()=="ar" else "Session expired","error")
            return redirect(safe_ref())
    return None

def _save_sess(user):
    l = session.get("lang","ar"); t = session.get("theme","light")
    session.clear()
    session.update(lang=l, theme=t, user_id=user["id"], username=user["username"],
                   role=user["role"], display_name=user["display_name"],
                   anonymous_code=user["anonymous_code"] or "",
                   is_anonymous=bool(user.get("is_anonymous",0)),
                   grade=user["grade"] or "",
                   supervised_grades=user["supervised_grades"] or "[]",
                   avatar_b64=user["avatar_b64"] or "",
                   _fp=_sfp(), new_badges_count=0)
    session.permanent = True

def _sg(): return get_supervised_grades_list(session.get("supervised_grades","[]"))

def _aerr(m,c=400): return jsonify({"error":True,"message":m,"code":c}),c
def _aok(d=None,**kw):
    r={"ok":True}
    if d: r["data"]=d
    r.update(kw); return jsonify(r)

def _jval():
    if request.content_length and request.content_length > 64000:
        return None, _aerr("payload too large",413)
    d = request.get_json(silent=True)
    if not isinstance(d, dict): return None, _aerr("invalid JSON",400)
    return d, None

def _clean(s, maxlen=5000): return re.sub(r"<[^>]+>","",str(s or "").strip())[:maxlen]
def _ip(): return (request.headers.get("X-Forwarded-For",request.remote_addr) or "x").split(",")[0].strip()

@app.route("/set-lang/<lang>")
def set_lang(lang): session["lang"] = lang if lang in ("ar","en") else "ar"; return redirect(safe_ref())
@app.route("/set-theme/<theme>")
def set_theme(theme): session["theme"] = theme if theme in ("light","dark") else "light"; return redirect(safe_ref())
@app.route("/robots.txt")
def robots(): return make_response("User-agent: *\nDisallow: /student\nDisallow: /counselor\nDisallow: /api\n",200,{"Content-Type":"text/plain"})
@app.route("/sitemap.xml")
def sitemap(): return make_response('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>/</loc></url></urlset>',200,{"Content-Type":"application/xml"})

@app.route("/ping")
def ping():
    import random
    if random.random() < 0.05:
        try:
            cleanup_rate_store()
            from database import get_db
            c=get_db(); c.execute("PRAGMA wal_checkpoint(PASSIVE)")
            c.execute("DELETE FROM lecture_log WHERE id NOT IN (SELECT id FROM lecture_log ORDER BY shown_at DESC LIMIT 1000)")
            c.commit(); c.close()
        except: pass
    return jsonify({"status":"ok","version":"v19","ts":int(time.time())}),200

@app.route("/health")
def health(): return jsonify({"status":"ok","version":"v19","ai":_gok(),"ts":int(time.time())})

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("counselor_dashboard" if session.get("role")=="counselor" else "student_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session: return redirect(url_for("index"))
    lang = _lang()
    if request.method == "POST":
        if request.form.get("honeypot"): return redirect(url_for("login"))
        if not rate_limit(f"login:{_ip()}",10,60):
            flash("محاولات كثيرة" if lang=="ar" else "Too many attempts","error")
            return render_template("login.html",lang=lang,theme=_theme())
        username = _clean(request.form.get("username",""),40)
        username = re.sub(r"[^a-zA-Z0-9_\u0600-\u06FF\-]","",username)
        password = request.form.get("password","")
        if not username or not password:
            flash("يرجى إدخال البيانات" if lang=="ar" else "Enter credentials","error")
            return render_template("login.html",lang=lang,theme=_theme())
        user = verify_login(username, password)
        if user:
            _save_sess(user)
            check_and_award_achievements(user["id"])
            return redirect(url_for("counselor_dashboard" if user["role"]=="counselor" else "student_dashboard"))
        time.sleep(0.15)  # prevent timing attacks
        flash("بيانات الدخول غير صحيحة" if lang=="ar" else "Invalid credentials","error")
    return render_template("login.html",lang=lang,theme=_theme())

@app.route("/register", methods=["GET","POST"])
def register():
    if "user_id" in session: return redirect(url_for("index"))
    lang = _lang()
    if request.method == "POST":
        if request.form.get("honeypot"): return redirect(url_for("register"))
        if not rate_limit(f"reg:{_ip()}",5,300):
            flash("محاولات كثيرة" if lang=="ar" else "Too many attempts","error")
            return render_template("register.html",lang=lang,theme=_theme())
        role = request.form.get("role","student")
        if role not in ("student","counselor"):
            flash("دور غير صالح" if lang=="ar" else "Invalid role","error")
            return render_template("register.html",lang=lang,theme=_theme())
        username = _clean(request.form.get("username",""),40)
        username = re.sub(r"[^a-zA-Z0-9_\u0600-\u06FF\-]","",username)
        password = request.form.get("password","")
        confirm  = request.form.get("confirm_password","")
        name     = _clean(request.form.get("display_name",""),120)
        grade    = request.form.get("grade") if role=="student" else None
        sup      = [g for g in request.form.getlist("supervised_grades") if g in GRADES] if role=="counselor" else None
        nid      = re.sub(r"[^0-9]","",(request.form.get("national_id") or "")) or None
        bday     = re.sub(r"[^0-9\-]","",(request.form.get("birthdate") or "")) or None
        if password and password.lower() == username.lower():
            flash("كلمة المرور لا تكون اسم المستخدم" if lang=="ar" else "Password can't be username","error")
            return render_template("register.html",lang=lang,theme=_theme())
        if grade and grade not in GRADES:
            flash("الصف غير صالح" if lang=="ar" else "Invalid grade","error")
            return render_template("register.html",lang=lang,theme=_theme())
        if password != confirm:
            flash("كلمات المرور غير متطابقة" if lang=="ar" else "Passwords don't match","error")
            return render_template("register.html",lang=lang,theme=_theme())
        ok, result = register_user(username, password, role, name, grade, sup, nid, bday)
        if ok:
            user = get_user_by_id(result)
            _save_sess(user)
            check_and_award_achievements(result)
            flash("أهلاً بك! 🎉" if lang=="ar" else "Welcome! 🎉","success")
            return redirect(url_for("counselor_dashboard" if role=="counselor" else "student_dashboard"))
        flash(result,"error")
    return render_template("register.html",lang=lang,theme=_theme())

@app.route("/register/anonymous", methods=["GET","POST"])
def register_anonymous():
    lang = _lang()
    if request.method == "POST":
        import string as _s
        ru = "anon_" + "".join(secrets.choice(_s.digits) for _ in range(6))
        rp = secrets.token_urlsafe(10)
        name  = _clean(request.form.get("display_name","مجهول الهوية"),60)
        grade = request.form.get("grade") or GRADES_AR[0]
        if grade not in GRADES: grade = GRADES_AR[0]
        ok, result = register_user(ru, rp, "student", name, grade, is_anonymous=True)
        if ok:
            user = get_user_by_id(result)
            _save_sess(user)
            session["anon_password"] = rp
            flash("تم إنشاء حساب مجهول ✅","success")
            return redirect(url_for("student_dashboard"))
        flash(result,"error")
    return render_template("register_anon.html",lang=lang,theme=_theme())

@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    lang = _lang()
    if request.method == "POST":
        if not rate_limit(f"forgot:{_ip()}",3,300):
            flash("محاولات كثيرة" if lang=="ar" else "Too many attempts","error")
            return render_template("forgot_password.html",lang=lang,theme=_theme())
        username = re.sub(r"[^a-zA-Z0-9_\u0600-\u06FF\-]","",_clean(request.form.get("username",""),40))
        from database import get_db
        conn=get_db(); u=conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",(username,)).fetchone(); conn.close()
        if u and u["national_id"] and u["birthdate"]:
            nid  = re.sub(r"[^0-9]","",request.form.get("national_id",""))
            bday = re.sub(r"[^0-9\-]","",request.form.get("birthdate",""))
            if secrets.compare_digest(nid, u["national_id"] or "") and bday == u["birthdate"]:
                temp_pw = secrets.token_urlsafe(8)
                change_password(u["id"], temp_pw)
                flash(f"{'كلمة المرور المؤقتة:' if lang=='ar' else 'Temporary password:'} {temp_pw}","success")
                return redirect(url_for("login"))
        time.sleep(0.2)
        flash("إذا كانت البيانات صحيحة سيتم الإرسال" if lang=="ar" else "If credentials match, temporary password issued","info")
    return render_template("forgot_password.html",lang=lang,theme=_theme())

@app.route("/logout")
def logout():
    l=session.get("lang","ar"); t=session.get("theme","light")
    session.clear(); session["lang"]=l; session["theme"]=t
    return redirect(url_for("login"))

@app.route("/student")
@login_required
def student_dashboard():
    uid=session["user_id"]; lang=_lang()
    user=get_user_by_id(uid)
    journals=get_student_journals(uid,limit=5)
    history=get_student_risk_history(uid,days=30)
    checkins=get_checkins(uid,limit=7)
    scores=[r["risk_score"] for r in history if r["risk_score"] is not None]
    labels=[r["created_at"][:10] for r in history]
    pred=predict_risk_trend(scores) if len(scores)>=3 else None
    lr=round(scores[-1],1) if scores else 0
    rl=("critical" if lr>=7.5 else "high" if lr>=5.0 else "medium" if lr>=2.5 else "low")
    lecture=get_today_lecture(uid)
    streak=get_streak(uid)
    badges=get_achievements(uid)[:3]
    return render_template("student_dashboard.html",
        user=user,journals=journals,checkins=checkins,
        chart_scores=json.dumps(scores),chart_labels=json.dumps(labels),
        prediction=pred,latest_risk=lr,risk_level=rl,
        lecture=lecture,streak=streak,achievements=badges,
        lang=lang,theme=_theme())

@app.route("/student/stats")
@login_required
def student_stats():
    uid=session["user_id"]
    stats=get_student_personal_stats(uid)
    history=get_student_risk_history(uid,days=60)
    scores=[r["risk_score"] for r in history if r["risk_score"] is not None]
    labels=[r["created_at"][:10] for r in history]
    sk=get_streak(uid)
    stats["current_streak"]=sk["current"]; stats["longest_streak"]=sk["longest"]
    checkins=get_checkins(uid,limit=30)
    mood_data=[{"date":c["created_at"][:10],"mood":c["mood"]} for c in checkins if c["created_at"]]
    return render_template("student_stats.html",
        stats=stats,chart_scores=json.dumps(scores),chart_labels=json.dumps(labels),
        mood_data=json.dumps(mood_data),lang=_lang(),theme=_theme())

@app.route("/student/profile", methods=["GET","POST"])
@login_required
def student_profile():
    uid=session["user_id"]; lang=_lang(); user=get_user_by_id(uid)
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        action=request.form.get("action","")
        if action == "update_info":
            nm=_clean(request.form.get("display_name",""),120)
            nid=re.sub(r"[^0-9]","",request.form.get("national_id","")) or None
            bday=re.sub(r"[^0-9\-]","",request.form.get("birthdate","")) or None
            if nm:
                update_user_profile(uid,display_name=nm,national_id=nid,birthdate=bday)
                session["display_name"]=nm
                flash("تم التحديث ✅" if lang=="ar" else "Updated ✅","success")
            else: flash("الاسم مطلوب" if lang=="ar" else "Name required","error")
        elif action == "change_password":
            old=request.form.get("old_password",""); new=request.form.get("new_password",""); conf=request.form.get("confirm_new_password","")
            if not verify_login(user["username"],old): flash("كلمة المرور الحالية خاطئة" if lang=="ar" else "Wrong current password","error")
            elif new != conf: flash("كلمات المرور غير متطابقة","error")
            elif new.lower() == user["username"].lower(): flash("كلمة المرور لا تكون اسم المستخدم","error")
            else:
                ok,err=change_password(uid,new)
                flash("تم التغيير ✅" if ok else err, "success" if ok else "error")
        elif action == "upload_avatar":
            f=request.files.get("avatar")
            if f and f.filename:
                ext=os.path.splitext(f.filename)[1].lower()
                if ext not in (".jpg",".jpeg",".png",".webp"): flash("يُسمح JPG/PNG/WebP فقط","error")
                else:
                    data=f.read(MAX_AVATAR_BYTES+1)
                    if len(data)>MAX_AVATAR_BYTES: flash("الصورة كبيرة جداً (حد 200KB)","error")
                    else:
                        mm={b'\xff\xd8\xff':'jpeg',b'\x89PNG':'png',b'RIFF':'webp'}
                        det=next((v for k,v in mm.items() if data[:len(k)]==k),None)
                        if not det: flash("ملف غير صالح","error")
                        else:
                            import base64 as _b
                            b64=f"data:image/{det};base64,"+_b.b64encode(data).decode()
                            update_user_profile(uid,avatar_b64=b64); session["avatar_b64"]=b64
                            flash("تم تحديث الصورة ✅","success")
            else: flash("لم يتم اختيار ملف","error")
        elif action == "delete_avatar":
            update_user_profile(uid,avatar_b64=""); session["avatar_b64"]=""
            flash("تم حذف الصورة","info")
        user=get_user_by_id(uid)
    return render_template("student_profile.html",user=user,lang=lang,theme=_theme())

@app.route("/journal", methods=["GET","POST"])
@login_required
def journal():
    uid=session["user_id"]; lang=_lang(); ar=None; rr=None
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        content=_clean(request.form.get("content",""),MAX_JOURNAL_LEN)
        try: mood=max(1,min(5,int(request.form.get("mood_score",3))))
        except: mood=3
        tc=count_today_journals(uid)
        if tc>=MAX_JOURNALS_DAY: flash(f"الحد الأقصى {MAX_JOURNALS_DAY} يوميات/يوم","error")
        elif len(content)<5: flash("يجب كتابة 5 أحرف على الأقل","error")
        elif len(content)>MAX_JOURNAL_LEN: flash(f"النص طويل (الحد {MAX_JOURNAL_LEN})","error")
        else:
            try:
                ai_sum=ai_adv=source_s=""
                if _gok():
                    ai_res=gemini.analyze_with_ai(content,lang)
                    if ai_res:
                        lc=gemini.quick_classify(content)
                        analysis={"lang":lc.get("lang",lang),"dominant_emotion":ai_res["emotion"],"confidence":ai_res["confidence"],"found_keywords":{"detected":ai_res.get("keywords",[])},"has_bullying":ai_res["emotion"]=="bullying","negative_hits":1 if ai_res["risk"]>2 else 0,"weighted_hits":ai_res["risk"]*0.5,"neg_density":ai_res["risk"]*5,"category_scores":{ai_res["emotion"]:ai_res["risk"]*2},"all_categories":[ai_res["emotion"]] if ai_res["emotion"]!="neutral" else [],"is_critical":ai_res.get("is_critical",False)}
                        risk={"score":ai_res["risk"],"max_score":10,"level":("critical" if ai_res["risk"]>=7.5 else "high" if ai_res["risk"]>=5.0 else "medium" if ai_res["risk"]>=2.5 else "low"),"color":("#9d174d" if ai_res["risk"]>=7.5 else "#ef4444" if ai_res["risk"]>=5.0 else "#f59e0b" if ai_res["risk"]>=2.5 else "#10b981"),"factors":{"AI":ai_res["risk"]},"should_alert":ai_res["risk"]>=RISK_THRESHOLD or ai_res.get("is_critical",False)}
                        ai_sum=ai_res.get("summary_ar",""); ai_adv=ai_res.get("advice_ar",""); source_s="gemini"
                    else:
                        analysis=analyze_text(content)
                        past=[r["risk_score"] for r in get_student_risk_history(uid) if r["risk_score"] is not None]
                        risk=calculate_risk_score(analysis,past)
                else:
                    analysis=analyze_text(content)
                    past=[r["risk_score"] for r in get_student_risk_history(uid) if r["risk_score"] is not None]
                    risk=calculate_risk_score(analysis,past)
                if not source_s: source_s="local"
                save_journal(uid,content,mood,analysis.get("lang",lang),analysis,risk,ai_sum,ai_adv,source_s)
                sr=update_streak(uid); nb=check_and_award_achievements(uid)
                session["new_badges_count"]=len(nb); session.modified=True
                if risk.get("should_alert"):
                    uo=get_user_by_id(uid)
                    save_alert(uid,uo["anonymous_code"] or "S-????",uo["grade"] or "",risk,analysis,lang)
                if sr.get("new_badge") or nb:
                    bn=(sr.get("new_badge") or {}).get("label_ar" if lang=="ar" else "label_en","")
                    if bn: flash(f"🎉 {'إنجاز جديد:' if lang=='ar' else 'Achievement:'} {bn}","badge")
                ar={**analysis,"ai_summary":ai_sum,"ai_advice":ai_adv,"source":source_s}; rr=risk
            except Exception as e:
                log.error(f"journal err: {e}")
                flash("حدث خطأ في التحليل","warning")
    recent=get_student_journals(uid,limit=8); tc2=count_today_journals(uid)
    return render_template("journal.html",analysis=ar,risk=rr,recent_journals=recent,today_count=tc2,max_journals=MAX_JOURNALS_DAY,max_length=MAX_JOURNAL_LEN,lang=lang,theme=_theme())

@app.route("/survey", methods=["GET","POST"])
@login_required
def survey():
    uid=session["user_id"]; lang=_lang(); result=None
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        if count_today_surveys(uid)>=MAX_SURVEYS_DAY:
            flash(f"الحد الأقصى {MAX_SURVEYS_DAY} استبيانات/يوم","error")
            return render_template("survey.html",lang=lang,theme=_theme(),result=None)
        ans={}
        for i in range(1,11):
            try: ans[f"q{i}"]=max(1,min(5,int(request.form.get(f"q{i}",3) or 3)))
            except: ans[f"q{i}"]=3
        notes=_clean(request.form.get("notes",""),MAX_NOTE_LEN)
        result=analyze_survey(ans); result["max_score"]=10
        save_survey(uid,ans,notes); check_and_award_achievements(uid)
        if result.get("should_alert"):
            uo=get_user_by_id(uid)
            save_alert(uid,uo["anonymous_code"] or "S-????",uo["grade"] or "",{"score":result["score"],"level":result["level"],"max_score":10},{"dominant_emotion":result.get("dominant_concern","neutral"),"has_bullying":False},lang)
    return render_template("survey.html",lang=lang,theme=_theme(),result=result)

@app.route("/checkin", methods=["POST"])
@login_required
def checkin():
    chk=verify_csrf()
    if chk: return chk
    uid=session["user_id"]; lang=_lang()
    if count_today_checkins(uid)>=MAX_CHECKINS_DAY:
        flash("✅ سجّلت حالتك اليوم","info")
        return redirect(url_for("student_dashboard"))
    try: mood=max(1,min(5,int(request.form.get("mood_score") or request.form.get("mood") or 3)))
    except: mood=3
    notes=_clean(request.form.get("notes",""),MAX_NOTE_LEN)
    save_checkin(uid,mood,int(bool(request.form.get("feeling_safe"))),int(bool(request.form.get("feeling_lonely"))),notes)
    sr=update_streak(uid); nb=check_and_award_achievements(uid)
    session["new_badges_count"]=len(nb); session.modified=True
    if sr.get("new_badge"):
        b=sr["new_badge"]; lbl=b.get("label_ar" if lang=="ar" else "label_en","إنجاز!")
        flash(f"🔥 {lbl} · ستريك {sr['current']} يوم!","success")
    elif sr.get("incremented"): flash(f"✅ تم التسجيل · 🔥 ستريك {sr['current']} يوم","success")
    else: flash("✅ تم تسجيل حالتك","success")
    return redirect(url_for("student_dashboard"))

@app.route("/companion", methods=["GET","POST"])
@login_required
def companion():
    lang=_lang(); resp=emo=breath=None
    if "chat_history" not in session: session["chat_history"]=[]
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        if not rate_limit(f"comp:{_ip()}",30,60):
            flash("محاولات كثيرة","error")
            return render_template("companion.html",response=None,emotion=None,breathing=None,has_ai=_gok(),chat_history=session.get("chat_history",[]),lang=lang,theme=_theme())
        msg=_clean(request.form.get("message",""),1000)
        if msg:
            lc=gemini.quick_classify(msg); emo=lc.get("dominant_emotion","neutral")
            hist=list(session.get("chat_history",[]))
            r=None
            if _gok(): r=gemini.get_nour_response(msg,lang,hist)
            if not r: r=get_companion_response(emo,lang,msg,history=hist)
            resp=r; hist.append({"role":"user","content":msg}); hist.append({"role":"assistant","content":resp})
            session["chat_history"]=hist[-(MAX_CHAT_HISTORY*2):]; session.modified=True
            if any(w in msg.lower() for w in ["تنفس","breath","تمرين","calm","هدئ"]):
                breath=BREATHING_EXERCISE.get(lang,BREATHING_EXERCISE["ar"])
    return render_template("companion.html",response=resp,emotion=emo,breathing=breath,has_ai=_gok(),chat_history=session.get("chat_history",[]),lang=lang,theme=_theme())

@app.route("/companion/reset", methods=["POST"])
@login_required
def companion_reset():
    chk=verify_csrf()
    if chk: return chk
    session["chat_history"]=[]; session.modified=True
    return jsonify({"ok":True})

@app.route("/emergency")
@login_required
def emergency(): return render_template("emergency.html",lang=_lang(),theme=_theme())

@app.route("/resources")
@login_required
def resources(): return render_template("resources.html",lang=_lang(),theme=_theme())

@app.route("/games")
@login_required
def games():
    uid=session["user_id"]
    ts={g:get_game_top_score(uid,g) for g in ("breathing","memory","positive","quiz")}
    return render_template("games.html",lang=_lang(),theme=_theme(),top_scores=ts)

@app.route("/goals", methods=["GET","POST"])
@login_required
def goals():
    uid=session["user_id"]; lang=_lang()
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        action=request.form.get("action","add")
        if action == "add":
            title=_clean(request.form.get("title",""),200)
            desc=_clean(request.form.get("description",""),1000)
            cat=request.form.get("category","personal")
            if cat not in ("personal","study","health","social","habit"): cat="personal"
            tdate=re.sub(r"[^0-9\-]","",request.form.get("target_date","")) or None
            if not title: flash("عنوان الهدف مطلوب","error")
            elif len(get_goals(uid,status="active"))>=MAX_GOALS_ACTIVE: flash(f"الحد الأقصى {MAX_GOALS_ACTIVE} هدف","error")
            else:
                save_goal(uid,title,desc,cat,tdate); check_and_award_achievements(uid)
                flash("تم إضافة الهدف ✅","success")
        elif action == "update_progress":
            gid=int(request.form.get("goal_id",0) or 0)
            prog=min(100,max(0,int(request.form.get("progress",0) or 0)))
            update_goal(gid,uid,progress=prog)
            if prog>=100: update_goal(gid,uid,status="completed"); check_and_award_achievements(uid); flash("🎉 أُنجز الهدف!","success")
        elif action == "complete":
            gid=int(request.form.get("goal_id",0) or 0)
            update_goal(gid,uid,status="completed",progress=100); check_and_award_achievements(uid)
            flash("🎉 تهانينا!","success")
        elif action == "delete":
            gid=int(request.form.get("goal_id",0) or 0)
            delete_goal(gid,uid); flash("تم الحذف","info")
        return redirect(url_for("goals"))
    ag=get_goals(uid); act=[g for g in ag if g["status"]=="active"]; don=[g for g in ag if g["status"]=="completed"]
    return render_template("goals.html",lang=lang,theme=_theme(),active_goals=act,done_goals=don,total=len(ag),completed=len(don),max_goals=MAX_GOALS_ACTIVE)

@app.route("/breathing-center")
@login_required
def breathing_center():
    uid=session["user_id"]
    return render_template("breathing_center.html",lang=_lang(),theme=_theme(),stats=get_breathing_stats(uid))

@app.route("/achievements")
@login_required
def achievements():
    uid=session["user_id"]
    check_and_award_achievements(uid)
    badges=get_achievements(uid); sk=get_streak(uid)
    session["new_badges_count"]=0; session.modified=True
    return render_template("achievements.html",lang=_lang(),theme=_theme(),badges=badges,streak=sk,all_badge_defs=BADGES)

@app.route("/about")
@login_required
def about(): return render_template("about.html",lang=_lang(),theme=_theme())
@app.route("/accessibility")
@login_required
def accessibility(): return render_template("accessibility.html",lang=_lang(),theme=_theme())

@app.route("/counselor")
@counselor_required
def counselor_dashboard():
    sg=_sg(); sts=get_students_for_counselor(sg or None); alts=get_alerts_for_counselor(sg or None,limit=30)
    stats=get_school_stats(sg); na=sum(1 for a in alts if a["status"]=="new")
    low=sum(1 for s in sts if not s["latest_level"] or s["latest_level"]=="low")
    med=sum(1 for s in sts if s["latest_level"]=="medium"); high=sum(1 for s in sts if s["latest_level"] in ("high","critical"))
    return render_template("counselor_dashboard.html",students=sts,alerts=alts,stats=stats,new_alerts=na,chart_dist=json.dumps([low,med,high]),supervised_grades=sg,lang=_lang(),theme=_theme())

@app.route("/counselor/profile", methods=["GET","POST"])
@counselor_required
def counselor_profile():
    uid=session["user_id"]; user=get_user_by_id(uid); lang=_lang()
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        action=request.form.get("action","")
        if action=="update_info":
            nm=_clean(request.form.get("display_name",""),120)
            if nm: update_user_profile(uid,display_name=nm); session["display_name"]=nm; flash("تم التحديث ✅","success")
        elif action=="change_password":
            op=request.form.get("old_password",""); np=request.form.get("new_password",""); cp=request.form.get("confirm_new_password","")
            if not verify_login(user["username"],op): flash("كلمة المرور الحالية خاطئة","error")
            elif np!=cp: flash("كلمات المرور غير متطابقة","error")
            else:
                ok,err=change_password(uid,np); flash("تم التغيير ✅" if ok else err,"success" if ok else "error")
        user=get_user_by_id(uid)
    return render_template("counselor_profile.html",user=user,lang=lang,theme=_theme())

@app.route("/counselor/students")
@counselor_required
def counselor_students():
    sg=_sg(); gf=request.args.get("grade","")
    sts=get_students_for_counselor(sg or None)
    if gf and gf in GRADES: sts=[s for s in sts if s["grade"]==gf]
    return render_template("counselor_students.html",students=sts,supervised_grades=sg,grade_filter=gf,lang=_lang(),theme=_theme())

@app.route("/counselor/students/<int:uid>/edit", methods=["GET","POST"])
@counselor_required
def counselor_edit_student(uid):
    st=get_user_by_id(uid)
    if not st: flash("الطالب غير موجود","error"); return redirect(url_for("counselor_students"))
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        counselor_update_student(uid,new_username=(_clean(request.form.get("username",""),40) or None),new_password=(_clean(request.form.get("new_password",""),128) or None),new_display_name=(_clean(request.form.get("display_name",""),120) or None))
        log_counselor_action(session["user_id"],"edit_student",f"uid={uid}")
        flash("تم التحديث ✅","success"); return redirect(url_for("counselor_students"))
    return render_template("counselor_edit_student.html",student=st,lang=_lang(),theme=_theme())

@app.route("/counselor/student/<int:uid>")
@counselor_required
def student_detail(uid):
    user=get_user_by_id(uid)
    if not user: flash("الطالب غير موجود","error"); return redirect(url_for("counselor_dashboard"))
    journals=get_student_journals(uid,limit=20); history=get_student_risk_history(uid,days=30)
    scores=[r["risk_score"] for r in history if r["risk_score"] is not None]; labels=[r["created_at"][:10] for r in history]
    pred=predict_risk_trend(scores) if len(scores)>=3 else None
    personal=get_student_personal_stats(uid); loc=get_student_location(uid); sk=get_streak(uid)
    return render_template("student_detail.html",student=user,journals=journals,personal_stats=personal,chart_scores=json.dumps(scores),chart_labels=json.dumps(labels),prediction=pred,location=loc,streak=sk,lang=_lang(),theme=_theme())

@app.route("/counselor/alert/<int:aid>/update", methods=["POST"])
@counselor_required
def update_alert(aid):
    chk=verify_csrf()
    if chk: return chk
    st=request.form.get("status","reviewed")
    if st not in ("new","reviewed","handled"): st="reviewed"
    update_alert_status(aid,st); log_counselor_action(session["user_id"],"update_alert",f"id={aid} status={st}")
    flash("تم التحديث ✅","success"); return redirect(url_for("counselor_dashboard"))

@app.route("/counselor/export-csv")
@counselor_required
def export_csv():
    import csv,io
    from datetime import datetime as _dt
    sg=_sg(); sts=get_students_for_counselor(sg or None)
    si=io.StringIO(); si.write('\ufeff'); w=csv.writer(si,quoting=csv.QUOTE_ALL)
    w.writerow(["الرمز","الصف","اليوميات","درجة الخطر","مستوى الخطر","ستريك","آخر تسجيل"])
    for s in sts: w.writerow([s["anonymous_code"] or "",s["grade"] or "",s["journal_count"] or 0,round(s["latest_risk"] or 0,1),s["latest_level"] or "low",s.get("current_streak",0),(s["last_entry"] or "")[:10]])
    resp=make_response(si.getvalue())
    resp.headers["Content-Disposition"]=f"attachment; filename=students_{_dt.now():%Y%m%d_%H%M}.csv"
    resp.headers["Content-Type"]="text/csv; charset=utf-8-sig"
    log_counselor_action(session["user_id"],"export_csv",f"n={len(sts)}")
    return resp

@app.route("/counselor/locations")
@counselor_required
def counselor_locations():
    sg=_sg(); locs=get_all_student_locations(sg if sg else None)
    lj=json.dumps([{"lat":l["latitude"],"lng":l["longitude"],"code":l["anonymous_code"] or "S-????","grade":l["grade"] or "","time":(l["shared_at"] or "")[:16],"city":l["city"] or "","uid":l["user_id"]} for l in locs])
    return render_template("counselor_locations.html",locations=locs,locs_json=lj,lang=_lang(),theme=_theme())

@app.route("/school-map")
@login_required
def school_map():
    if session.get("role")=="counselor":
        sg=_sg(); stats=get_school_stats(sg if sg else None)
        return render_template("school_map.html",stats=stats,role="counselor",lang=_lang(),theme=_theme())
    return redirect(url_for("student_stats"))

# API
@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    if not rate_limit(f"api:{_ip()}",60,60): return _aerr("rate limited",429)
    if not request.is_json: return _aerr("JSON required",400)
    d,e=_jval()
    if e: return e
    text=_clean(d.get("text",""),5000)
    if len(text)<3: return _aerr("too short")
    try: return jsonify(analyze_text(text))
    except Exception as ex: log.error(f"api_analyze: {ex}"); return _aerr("failed",500)

@app.route("/api/companion", methods=["POST"])
@login_required
def api_companion():
    uid=session.get("user_id","x")
    if not rate_limit(f"comp:{_ip()}",30,60): return _aerr("rate limited",429)
    if not rate_limit(f"comp_u:{uid}",60,300): return _aerr("rate limited",429)
    if not request.is_json: return _aerr("JSON required",400)
    d,e=_jval()
    if e: return e
    msg=_clean(d.get("message",""),1000)
    if not msg: return _aerr("empty")
    lang=_lang(); lc=gemini.quick_classify(msg); hist=list(session.get("chat_history",[]))
    r=None
    if _gok(): r=gemini.get_nour_response(msg,lang,hist)
    if not r: r=get_companion_response(lc.get("dominant_emotion","neutral"),lang,msg,history=hist)
    hist.append({"role":"user","content":msg}); hist.append({"role":"assistant","content":r})
    session["chat_history"]=hist[-(MAX_CHAT_HISTORY*2):]; session.modified=True
    return jsonify({"response":r,"emotion":lc.get("dominant_emotion","neutral")})

@app.route("/api/daily-status")
@login_required
def api_daily_status():
    uid=session["user_id"]
    return jsonify({"journals_today":count_today_journals(uid),"checkins_today":count_today_checkins(uid),"surveys_today":count_today_surveys(uid),"journals_max":MAX_JOURNALS_DAY,"checkins_max":MAX_CHECKINS_DAY,"surveys_max":MAX_SURVEYS_DAY})

@app.route("/api/mood-trend")
@login_required
def api_mood_trend():
    uid=session["user_id"]; h=get_student_risk_history(uid,days=14)
    d=[{"date":r["created_at"][:10],"score":r["risk_score"],"emotion":r["dominant_emotion"]} for r in h if r["risk_score"] is not None]
    return jsonify({"data":d,"count":len(d)})

@app.route("/api/location", methods=["POST"])
@login_required
def api_save_location():
    chk=verify_csrf()
    if chk: return chk
    if not request.is_json: return _aerr("JSON required",400)
    d,e=_jval()
    if e: return e
    try:
        lat=float(d.get("latitude",0)); lng=float(d.get("longitude",0))
        if not (-90<=lat<=90 and -180<=lng<=180): return _aerr("invalid coords")
        city=_clean(d.get("city",""),100) or None
        save_location(session["user_id"],lat,lng,d.get("accuracy"),city)
        return _aok(message="تم حفظ الموقع")
    except (ValueError,TypeError): return _aerr("invalid coords")

@app.route("/api/game-score", methods=["POST"])
@login_required
def api_game_score():
    chk=verify_csrf()
    if chk: return chk
    if not request.is_json: return _aerr("JSON required",400)
    d,e=_jval()
    if e: return e
    game=str(d.get("game","")).strip()[:50]
    try:
        score=max(0,int(d.get("score",0) or 0))
        level=max(1,min(99,int(d.get("level",1) or 1)))
        dur=max(0,int(d.get("duration",0) or 0))
    except (ValueError,TypeError): return _aerr("invalid score")
    if not game: return _aerr("missing game")
    save_game_score(session["user_id"],game,score,level,dur)
    nb=check_and_award_achievements(session["user_id"])
    top=get_game_top_score(session["user_id"],game)
    return _aok(top_score=top,is_new_record=(score>=top and score>0),new_badges=len(nb))

@app.route("/api/breathing-done", methods=["POST"])
@login_required
def api_breathing_done():
    chk=verify_csrf()
    if chk: return chk
    if not request.is_json: return _aerr("JSON required",400)
    d,e=_jval()
    if e: return e
    tech=str(d.get("technique","4-7-8"))
    if tech not in ("4-7-8","box","calm"): tech="4-7-8"
    try: cyc=max(0,int(d.get("cycles",0) or 0)); dur=max(0,int(d.get("duration",0) or 0))
    except: cyc=dur=0
    if cyc<1: return _aerr("no cycles")
    mb=d.get("mood_before"); ma=d.get("mood_after")
    if mb is not None:
        try: mb=max(1,min(5,int(mb)))
        except: mb=None
    if ma is not None:
        try: ma=max(1,min(5,int(ma)))
        except: ma=None
    save_breathing_session(session["user_id"],tech,cyc,dur,mb,ma)
    check_and_award_achievements(session["user_id"])
    return _aok(message="جلسة التنفس محفوظة ✅")

@app.route("/api/streak")
@login_required
def api_streak(): return jsonify(get_streak(session["user_id"]))

@app.route("/api/quick-stats")
@login_required
def api_quick_stats(): return jsonify(get_student_personal_stats(session["user_id"]))

@app.route("/api/search-students")
@counselor_required
def api_search_students():
    q=re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s\-]","",request.args.get("q","")).strip().lower()
    sg=_sg(); sts=get_students_for_counselor(sg or None)
    if q: sts=[s for s in sts if q in (s["anonymous_code"] or "").lower() or q in (s["grade"] or "").lower() or q in (s["display_name"] or "").lower()]
    return jsonify([dict(s) for s in sts[:30]])

@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback():
    d=request.get_json(silent=True) or {}
    fb=_clean(d.get("feedback",""),500)
    if fb: log.info(f"Feedback uid={session.get('user_id')}: {fb[:100]}")
    return _aok()

@app.route("/api/password-strength", methods=["POST"])
def api_password_strength():
    """Return password strength score."""
    if not request.is_json: return _aerr("JSON required", 400)
    d = request.get_json(silent=True) or {}
    pw = str(d.get("password",""))
    score, lbl_ar, lbl_en = password_strength_score(pw)
    return jsonify({"score":score,"label":lbl_ar if _lang()=="ar" else lbl_en,"max":4})

@app.route("/api/tips", methods=["GET","POST"])
@login_required
def api_tips():
    if request.method == "POST":
        chk=verify_csrf()
        if chk: return chk
        d=request.get_json(silent=True) or {}
        tip=_clean(d.get("tip_ar",""),300)
        if len(tip)<5: return _aerr("too short")
        submit_tip(session["user_id"],tip,category=d.get("category","general"))
        return _aok()
    return jsonify([dict(t) for t in get_approved_tips(20)])


@app.route("/api/statistics")
@login_required
def api_statistics():
    """Global statistics for research dashboard."""
    uid = session["user_id"]
    role = session.get("role","student")
    lang = _lang()
    if role == "counselor":
        sg = _sg()
        stats = get_school_stats(sg or None)
        alerts = get_alerts_for_counselor(sg or None, limit=100)
        trend_data = []
        from database import get_db
        conn = get_db()
        rows = conn.execute(
            "SELECT DATE(created_at) as d, AVG(risk_score) as avg_r, COUNT(*) as cnt "
            "FROM emotion_analysis WHERE created_at >= datetime('now','-30 days') "
            "GROUP BY DATE(created_at) ORDER BY d ASC"
        ).fetchall()
        conn.close()
        trend_data = [{"date":r["d"],"avg_risk":round(r["avg_r"],2),"count":r["cnt"]} for r in rows]
        return jsonify({"stats":dict(stats),"trend":trend_data,"alert_counts":count_alerts_by_status(sg or None)})
    else:
        personal = get_student_personal_stats(uid)
        return jsonify(personal)

@app.route("/research")
@login_required
def research_dashboard():
    """Research & experiment dashboard."""
    if session.get("role") != "counselor":
        return redirect(url_for("student_stats"))
    sg = _sg()
    stats = get_school_stats(sg or None)
    from database import get_db
    conn = get_db()
    # Emotion distribution
    emo_rows = conn.execute(
        "SELECT dominant_emotion, COUNT(*) as c FROM emotion_analysis "
        "GROUP BY dominant_emotion ORDER BY c DESC"
    ).fetchall()
    # Risk trend last 30 days
    trend_rows = conn.execute(
        "SELECT DATE(created_at) as d, AVG(risk_score) as avg_r "
        "FROM emotion_analysis WHERE created_at >= datetime('now','-30 days') "
        "GROUP BY DATE(created_at) ORDER BY d"
    ).fetchall()
    # Accuracy metrics (simulated from real analysis counts)
    acc_rows = conn.execute(
        "SELECT risk_level, COUNT(*) as c FROM emotion_analysis GROUP BY risk_level"
    ).fetchall()
    conn.close()
    emo_data = [{"emotion":r["dominant_emotion"],"count":r["c"]} for r in emo_rows]
    trend_data = [{"date":r["d"],"avg_risk":round(r["avg_r"],2)} for r in trend_rows]
    acc_data = {r["risk_level"]:r["c"] for r in acc_rows}
    return render_template("research.html",
        lang=_lang(), theme=_theme(),
        stats=stats, emo_data=json.dumps(emo_data),
        trend_data=json.dumps(trend_data),
        acc_data=json.dumps(acc_data))

@app.route("/export-report")
@login_required
def export_report():
    """Export personal wellness report as text."""
    uid = session["user_id"]
    lang = _lang()
    stats = get_student_personal_stats(uid)
    history = get_student_risk_history(uid, days=30)
    journals = get_student_journals(uid, limit=5)
    sk = get_streak(uid)
    badges = get_achievements(uid)
    from datetime import datetime as _dt
    lines = []
    lines.append(f"SchoolMind AI — {'تقرير صحتي النفسية' if lang=='ar' else 'My Wellness Report'}")
    lines.append(f"{'التاريخ' if lang=='ar' else 'Date'}: {_dt.now().strftime('%Y-%m-%d')}")
    lines.append("="*50)
    lines.append(f"{'الشعلة الحالية' if lang=='ar' else 'Current Streak'}: {sk['current']} {'يوم' if lang=='ar' else 'days'}")
    lines.append(f"{'إجمالي اليوميات' if lang=='ar' else 'Total Journals'}: {stats['total_journals']}")
    lines.append(f"{'متوسط درجة الخطر' if lang=='ar' else 'Avg Risk Score'}: {stats['avg_risk']}/10")
    lines.append(f"{'الإنجازات' if lang=='ar' else 'Achievements'}: {stats['achievements_count']}")
    lines.append("="*50)
    lines.append(f"{'آخر ٥ يوميات' if lang=='ar' else 'Last 5 Journals'}:")
    for j in journals:
        lines.append(f"  - {(j['created_at'] or '')[:10]}: {(j['content'] or '')[:60]}...")
    content = "\n".join(lines)
    resp = make_response(content)
    resp.headers["Content-Disposition"] = f"attachment; filename=wellness_report_{_dt.now():%Y%m%d}.txt"
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp

@app.errorhandler(400)
def e400(e):
    if request.is_json or request.path.startswith("/api/"): return _aerr("Bad request",400)
    flash("طلب غير صحيح","error"); return redirect(safe_ref())
@app.errorhandler(403)
def e403(e):
    if request.is_json or request.path.startswith("/api/"): return _aerr("Forbidden",403)
    flash("انتهت صلاحية الجلسة","error"); return redirect(safe_ref())
@app.errorhandler(404)
def e404(e): return render_template("404.html",lang=_lang(),theme=_theme()),404
@app.errorhandler(413)
def e413(e): flash("الملف كبير جداً","error"); return redirect(safe_ref())
@app.errorhandler(429)
def e429(e):
    if request.is_json or request.path.startswith("/api/"): return _aerr("Rate limited",429)
    flash("محاولات كثيرة","error"); return redirect(safe_ref())
@app.errorhandler(500)
def e500(e):
    log.error(f"500: {e}")
    if request.is_json or request.path.startswith("/api/"): return _aerr("Server error",500)
    flash("خطأ في الخادم","error"); return redirect(url_for("index"))

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"\n  SchoolMind AI v19 · http://127.0.0.1:{port}\n")
    app.run(debug=os.environ.get("FLASK_DEBUG","1")=="1",host="0.0.0.0",port=port)
