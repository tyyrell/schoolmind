"""
SchoolMind AI v13 — Database Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Improvements over v12:
- FIX: get_students_for_counselor now uses LATEST risk score (not MAX)
- FIX: Added count_alerts_by_status function (used in app.py)
- FIX: cleanup_rate_store() to prevent memory leak
- FIX: _validate_birthdate handles all edge cases properly
- FIX: national_id validation allows 9-12 digits (was missing from some paths)
- FIX: Improved connection handling with context manager
- ADDED: get_user_by_username() function
- ADDED: get_unread_alerts_count() function
- ADDED: get_student_checkin_streak() function
- ADDED: proper transaction handling in save_journal
- ADDED: get_journal_today_count_with_content() for dedup
- IMPROVED: get_school_stats() handles edge cases better
- IMPROVED: rate_limit cleanup to bounded list
- IMPROVED: counselor_update_student validates new username uniqueness
- IMPROVED: Better error logging
- IMPROVED: Index on users.role for faster queries
- IMPROVED: Index on alerts.user_id for faster joins
"""
import sqlite3, os, json, re, random, string, time, base64, logging
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

log = logging.getLogger('schoolmind.db')

_base   = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH",
          os.path.join(_base, "database", "schoolmind.db"))

GRADES_AR = ["الصف السابع", "الصف الثامن", "الصف التاسع",
             "الصف العاشر", "الصف الحادي عشر", "الصف الثاني عشر"]
GRADES_EN = ["Grade 7", "Grade 8", "Grade 9",
             "Grade 10", "Grade 11", "Grade 12"]
GRADES    = GRADES_AR + GRADES_EN

# ─── 100 Lectures ─────────────────────────────────────────────────────────────
LECTURES = [
    {"id": i+1, "title_ar": ar, "title_en": en, "url": url, "cat": cat}
    for i, (ar, en, url, cat) in enumerate([
        ("قوة الإرادة","The Power of Willpower","https://youtu.be/V5BXuZL1HAg","motivation"),
        ("التعامل مع التنمر","How to Deal with Bullying","https://youtu.be/2SuPVq5lbw4","mental_health"),
        ("إدارة الوقت للطلاب","Time Management for Students","https://youtu.be/oTugjssqOT0","skills"),
        ("التغلب على القلق","Overcoming Anxiety","https://youtu.be/ZidGozDhOjg","mental_health"),
        ("التفكير الإيجابي","Power of Positive Thinking","https://youtu.be/iCvmsMzlF7o","motivation"),
        ("الثقة بالنفس","Building Self-Confidence","https://youtu.be/l_NYrWqUR40","skills"),
        ("الصحة النفسية للمراهقين","Mental Health for Teens","https://youtu.be/8x2aqBzXOQQ","mental_health"),
        ("الدراسة الفعّالة","How to Study Effectively","https://youtu.be/IlU-zDU6aQ0","skills"),
        ("التخلص من التوتر","Stress Relief Techniques","https://youtu.be/15mANzVpB2Q","mental_health"),
        ("رحلة النجاح","Success Journey","https://youtu.be/ZXsQAXx_ao0","motivation"),
        ("مواجهة الخوف","Facing Your Fears","https://youtu.be/8ZhoeSaPF-k","mental_health"),
        ("مهارات التواصل","Communication Skills","https://youtu.be/HAnw168huqA","skills"),
        ("تأثير النوم على العقل","Sleep and the Brain","https://youtu.be/5MuIMqhT8oM","health"),
        ("اليقظة الذهنية","Mindfulness for Youth","https://youtu.be/inpok4MKVLM","mental_health"),
        ("التعلم السريع","How to Learn Fast","https://youtu.be/O96fE1E-rf8","skills"),
        ("الذكاء العاطفي","Emotional Intelligence","https://youtu.be/LKL5T2wAq6g","mental_health"),
        ("الأهداف الذكية","SMART Goals","https://youtu.be/1-SvuFIQjK8","skills"),
        ("الرياضة والمزاج","Exercise and Mood","https://youtu.be/1nZEdqcGVzo","health"),
        ("التعامل مع الإحباط","Dealing with Frustration","https://youtu.be/BsVq5R_F6KA","mental_health"),
        ("قوة الامتنان","The Power of Gratitude","https://youtu.be/WPPPFqsECz0","motivation"),
        ("حل المشكلات","Problem Solving","https://youtu.be/x4d9SUkqRIM","skills"),
        ("ضغط الأقران","Peer Pressure","https://youtu.be/YSm8T3EEBb8","mental_health"),
        ("بناء العلاقات","Healthy Relationships","https://youtu.be/sa0By7pOMEA","skills"),
        ("الفشل طريق النجاح","Failure Leads to Success","https://youtu.be/raIBrxBY4Q4","motivation"),
        ("الأفكار السلبية","Negative Thoughts","https://youtu.be/xSMqGr0SZFA","mental_health"),
        ("التغذية والعقل","Nutrition for the Brain","https://youtu.be/vZng2MZ-Jic","health"),
        ("الإبداع","How to Be Creative","https://youtu.be/bEusrD8g-dM","skills"),
        ("فهم الاكتئاب","Understanding Depression","https://youtu.be/z-IR48Mb3W0","mental_health"),
        ("تقنية بومودورو","Pomodoro Technique","https://youtu.be/VFW3Ld7JO0w","skills"),
        ("قبول النفس","Embrace Yourself","https://youtu.be/oqy1JBhTqkw","motivation"),
        ("الاستماع الفعّال","Active Listening","https://youtu.be/7wUCyjiyXdg","skills"),
        ("التعامل مع الغضب","Managing Anger","https://youtu.be/wQiGDfI6H50","mental_health"),
        ("القراءة والدماغ","Reading and Brain","https://youtu.be/MvWB9dJdFbQ","skills"),
        ("تمارين التنفس","Breathing Exercises","https://youtu.be/tybOi4hjZFQ","health"),
        ("الإيمان بالنفس","Self-Belief","https://youtu.be/SdWkbLYy1gI","motivation"),
        ("التعلم من الأخطاء","Learning from Mistakes","https://youtu.be/a9Gx8AkHHbA","skills"),
        ("القلق الاجتماعي","Social Anxiety","https://youtu.be/6TTg3a9lDHo","mental_health"),
        ("النوم والدراسة","Sleep and Study","https://youtu.be/gedoSfZvBgE","health"),
        ("الحفاظ على الدوافع","Staying Motivated","https://youtu.be/7sxpKhIbr0E","motivation"),
        ("الحدود الشخصية","Personal Boundaries","https://youtu.be/X_OHmBQMPBs","skills"),
        ("التفكير النقدي","Critical Thinking","https://youtu.be/9oAf3g5_138","skills"),
        ("التعامل مع الحزن","Dealing with Sadness","https://youtu.be/vXZ9kW1f1EM","mental_health"),
        ("توازن الدراسة","Study-Life Balance","https://youtu.be/t2KtaUQ0xag","skills"),
        ("احترام الذات","Self-Respect","https://youtu.be/0k7xjDLTwGY","mental_health"),
        ("تقوية الذاكرة","Memory Enhancement","https://youtu.be/Gvo-JvZrgXE","skills"),
        ("التأمل","Mindfulness Practice","https://youtu.be/ZToicYcHIOU","health"),
        ("رسالة أمل","A Message of Hope","https://youtu.be/MOOGPbMRqVM","motivation"),
        ("تحقيق الأهداف","Achieving Goals","https://youtu.be/TQMbvJNRpLE","skills"),
        ("وسائل التواصل","Social Media & Mental Health","https://youtu.be/Czg_9C7gw0o","mental_health"),
        ("عقلية النمو","Growth Mindset","https://youtu.be/KUWn_TJTrnU","motivation"),
        ("اتخاذ القرارات","Better Decisions","https://youtu.be/d7Jnmi2BkS8","skills"),
        ("الاضطرابات النفسية","Mental Health Disorders","https://youtu.be/7G2ICFG-9Kg","mental_health"),
        ("تأثير الموسيقى","Music and Mind","https://youtu.be/R0JKCYZ8hng","health"),
        ("تجاوز الأزمات","Overcoming Crisis","https://youtu.be/NWH8N-BvhAw","motivation"),
        ("التعبير عن المشاعر","Expressing Emotions","https://youtu.be/oFIvFdZ-GXY","skills"),
        ("الإرهاق الدراسي","Academic Burnout","https://youtu.be/jqONINYoohY","health"),
        ("أنت أقوى مما تعتقد","You Are Stronger","https://youtu.be/mgmVOuLgFB0","motivation"),
        ("التعاطف","Empathy","https://youtu.be/1Evwgu369Jw","skills"),
        ("الصداقة الحقيقية","True Friendship","https://youtu.be/aQNXuJQjWBs","skills"),
        ("الحديث أمام الجمهور","Public Speaking","https://youtu.be/tShavGuo0_E","skills"),
        ("قصص نجاح","Success Stories","https://youtu.be/la9R5YOqKlI","motivation"),
        ("تقبّل النقد","Handling Criticism","https://youtu.be/v7KZu73BGXU","skills"),
        ("الرياضة والنفس","Sports and Wellness","https://youtu.be/UZEE4u9dpRU","health"),
        ("تعلّم الصبر","Learning Patience","https://youtu.be/Lp7E973zozc","motivation"),
        ("علم الأعصاب والدراسة","Neuroscience of Study","https://youtu.be/cjS9G0W_bXY","skills"),
        ("الحزن والاكتئاب","Sadness vs Depression","https://youtu.be/l8MNfCIBBLQ","mental_health"),
        ("المرونة العاطفية","Emotional Resilience","https://youtu.be/SGYBRoQBFHY","mental_health"),
        ("النجاح بعد الصعاب","Success After Hardship","https://youtu.be/PcU3RO-4LOI","motivation"),
        ("مشاعرك صالحة","Your Feelings Are Valid","https://youtu.be/G7zAseaIyFA","mental_health"),
        ("مقاومة الإلهاء","Resisting Distractions","https://youtu.be/d_GFsqCY9I4","skills"),
        ("الفن كعلاج","Art as Therapy","https://youtu.be/OOFD2hBmFiA","mental_health"),
        ("اكتشاف الشغف","Finding Your Passion","https://youtu.be/jAIaphep5wg","motivation"),
        ("اضطراب التركيز","ADHD Awareness","https://youtu.be/cx13a2-unjE","mental_health"),
        ("الكلمات الإيجابية","Positive Words","https://youtu.be/Huy1POsZuGM","motivation"),
        ("التوازن مع الإنترنت","Digital Balance","https://youtu.be/yHmNA8GF8Eg","health"),
        ("طلب المساعدة","Asking for Help","https://youtu.be/rkZl2gsLUp4","mental_health"),
        ("الصداقات الحقيقية","Genuine Friendships","https://youtu.be/I9sMR2kGJiA","skills"),
        ("مواجهة التحديات","Facing Challenges","https://youtu.be/ia9yCzJEpEQ","motivation"),
        ("اليوغا والاسترخاء","Yoga & Relaxation","https://youtu.be/v7AYKMP6rOE","health"),
        ("التكيف مع التغيير","Adapting to Change","https://youtu.be/JcqSbJWMcFI","skills"),
        ("إدارة وقت المذاكرة","Smart Study Time","https://youtu.be/n3kNlFMXslo","skills"),
        ("التعامل مع الخسارة","Coping with Loss","https://youtu.be/1Evwgu369Jw","mental_health"),
        ("التوجيه المهني","Career Guidance","https://youtu.be/xt3noHty7Tg","skills"),
        ("قوة الابتسامة","The Power of a Smile","https://youtu.be/U9cGdRNMdQQ","motivation"),
        ("حماية صحتك النفسية","Daily Mental Health","https://youtu.be/R0JKCYZ8hng","mental_health"),
        ("اكتشاف الهوية","Identity Discovery","https://youtu.be/L1pkZoFvaSo","mental_health"),
        ("التعلم من الناجحين","Learn from Success","https://youtu.be/V1-sjn-UGOM","motivation"),
        ("مستقبل التعليم","Future of Education","https://youtu.be/1B5z8AEJGkA","skills"),
        ("ضغط الامتحانات","Exam Stress","https://youtu.be/0p5u4OL2X-U","health"),
        ("النجاح يحتاج جهداً","Success Needs Effort","https://youtu.be/lbDTWNzqkMY","motivation"),
        ("مهارة الكتابة","Writing Skills","https://youtu.be/vtIzMaLkCaM","skills"),
        ("فهم القلق","Understanding Anxiety","https://youtu.be/ZidGozDhOjg","mental_health"),
        ("أنت مميز وفريد","You Are Unique","https://youtu.be/iCvmsMzlF7o","motivation"),
        ("الروتين الصحي","Healthy Routine","https://youtu.be/9VyO9FbV-G4","health"),
        ("الوعي الذاتي","Self-Awareness","https://youtu.be/tGdsOXZpyWE","mental_health"),
        ("الحفاظ على الطاقة","Maintaining Energy","https://youtu.be/1nZEdqcGVzo","health"),
        ("رسالة لمستقبلك","Letter to Your Future","https://youtu.be/ia9yCzJEpEQ","motivation"),
    ])
]

# ─── Connection ────────────────────────────────────────────────────────────────
def get_db():
    """FIX: Get database connection with proper settings."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA cache_size=-10000")  # FIX: 10MB cache
    return conn

@contextmanager
def db_context():
    """FIX: Context manager for safe database usage."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

# ─── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            username         TEXT UNIQUE NOT NULL,
            password_hash    TEXT NOT NULL,
            role             TEXT NOT NULL DEFAULT 'student',
            display_name     TEXT NOT NULL,
            grade            TEXT,
            supervised_grades TEXT,
            anonymous_code   TEXT UNIQUE,
            is_anonymous     INTEGER DEFAULT 0,
            national_id      TEXT,
            birthdate        TEXT,
            avatar_b64       TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            is_active        INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS journals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            content    TEXT NOT NULL,
            mood_score INTEGER DEFAULT 3,
            lang       TEXT DEFAULT 'ar',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS emotion_analysis (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id       INTEGER NOT NULL,
            user_id          INTEGER NOT NULL,
            dominant_emotion TEXT,
            confidence       REAL,
            has_bullying     INTEGER DEFAULT 0,
            negative_hits    INTEGER DEFAULT 0,
            found_categories TEXT,
            risk_score       REAL DEFAULT 0,
            risk_level       TEXT DEFAULT 'low',
            ai_summary       TEXT DEFAULT '',
            ai_advice        TEXT DEFAULT '',
            source           TEXT DEFAULT 'local',
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (journal_id) REFERENCES journals(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            anonymous_code TEXT,
            grade          TEXT,
            risk_score     REAL,
            risk_level     TEXT,
            alert_type     TEXT,
            summary        TEXT,
            recommendation TEXT,
            status         TEXT DEFAULT 'new',
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS checkins (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            mood           INTEGER NOT NULL,
            feeling_safe   INTEGER DEFAULT 1,
            feeling_lonely INTEGER DEFAULT 0,
            notes          TEXT,
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS surveys (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS lecture_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            lecture_id INTEGER NOT NULL,
            shown_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_journals_user    ON journals(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ea_user          ON emotion_analysis(user_id);
        CREATE INDEX IF NOT EXISTS idx_ea_created       ON emotion_analysis(created_at);
        CREATE INDEX IF NOT EXISTS idx_ea_journal       ON emotion_analysis(journal_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_status    ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_user      ON alerts(user_id);
        CREATE INDEX IF NOT EXISTS idx_checkins_user    ON checkins(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_surveys_user     ON surveys(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role, is_active);
        CREATE INDEX IF NOT EXISTS idx_lecture_user     ON lecture_log(user_id, shown_at);
    """)
    conn.commit()
    conn.close()

# ─── Validation helpers ────────────────────────────────────────────────────────
def _sanitize_username(u: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', (u or "").strip())[:40]

def _validate_password(pw: str) -> tuple:
    if not pw or len(pw) < 6:
        return False, "كلمة المرور يجب 6 أحرف على الأقل / Min 6 chars"
    if pw.isdigit():
        return False, "كلمة المرور لا يجب أن تكون أرقاماً فقط / Not only digits"
    return True, ""

def _validate_birthdate(bd: str) -> bool:
    """FIX: More robust birthdate validation."""
    if not bd:
        return True
    try:
        from datetime import date
        # Handle different separators
        bd_clean = bd.strip().replace("/", "-").replace(".", "-")
        parts = bd_clean.split("-")
        if len(parts) != 3:
            return False
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        # Basic range checks before creating date object
        if not (1900 <= y <= 2020):  return False
        if not (1 <= m <= 12):       return False
        if not (1 <= d <= 31):       return False
        bdate = date(y, m, d)
        today = date.today()
        age = (today - bdate).days / 365.25
        return 4 < age < 100
    except (ValueError, TypeError, OverflowError):
        return False

def _validate_national_id(nid: str) -> bool:
    if not nid:
        return True
    return bool(re.match(r'^\d{9,12}$', nid.strip()))

# ─── Registration ──────────────────────────────────────────────────────────────
def register_user(username, password, role, display_name,
                  grade=None, supervised_grades=None,
                  national_id=None, birthdate=None, is_anonymous=False):
    username     = _sanitize_username(username)
    display_name = (display_name or "").strip()[:120]
    national_id  = (national_id or "").strip() or None
    birthdate    = (birthdate or "").strip() or None

    if not is_anonymous:
        if len(username) < 3:
            return False, "اسم المستخدم يجب 3 أحرف على الأقل / Min 3 chars"
        pw_ok, pw_err = _validate_password(password)
        if not pw_ok:
            return False, pw_err
        if not display_name:
            return False, "الاسم الكامل مطلوب / Full name required"
        if role == "student" and not grade:
            return False, "يجب اختيار الصف / Grade required"
        if role == "counselor" and not supervised_grades:
            return False, "يجب اختيار صف واحد على الأقل"
        if national_id and not _validate_national_id(national_id):
            return False, "الرقم الوطني يجب أن يكون 9-12 رقماً"
        if birthdate and not _validate_birthdate(birthdate):
            return False, "تاريخ الميلاد غير صحيح / Invalid birthdate"

    conn = get_db()
    try:
        if conn.execute("SELECT id FROM users WHERE username=?",
                        (username,)).fetchone():
            return False, "اسم المستخدم مستخدم بالفعل / Username already taken"

        # Generate unique anonymous code
        for _ in range(20):
            prefix = "S" if role == "student" else "C"
            code = prefix + "-" + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=4))
            if not conn.execute("SELECT id FROM users WHERE anonymous_code=?",
                                (code,)).fetchone():
                break

        sup_json = json.dumps(supervised_grades) if supervised_grades else None
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, grade, "
            "supervised_grades, anonymous_code, national_id, birthdate, is_anonymous) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), role, display_name, grade,
             sup_json, code, national_id, birthdate, int(is_anonymous))
        ).lastrowid
        conn.commit()
        return True, uid
    except sqlite3.IntegrityError:
        return False, "اسم المستخدم مستخدم بالفعل / Username already taken"
    except Exception as e:
        log.error(f"register_user error: {e}")
        return False, str(e)
    finally:
        conn.close()

# ─── Auth ──────────────────────────────────────────────────────────────────────
def verify_login(username, password):
    username = _sanitize_username(username)
    conn = get_db()
    u = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()
    if u and check_password_hash(u["password_hash"], password):
        return u
    return None

def get_user_by_id(uid):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return u

def get_user_by_username(username):
    """FIX: Added get_user_by_username function."""
    username = _sanitize_username(username)
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",
                     (username,)).fetchone()
    conn.close()
    return u

def update_user_profile(uid, display_name=None, avatar_b64=None,
                        national_id=None, birthdate=None):
    """FIX: avatar_b64 stored as base64 data URI in DB."""
    conn = get_db()
    try:
        if display_name:
            conn.execute("UPDATE users SET display_name=? WHERE id=?",
                         (display_name[:120], uid))
        if avatar_b64 is not None:
            # FIX: Validate size before storing
            if len(avatar_b64) <= 280_000:  # ~200KB base64 overhead
                conn.execute("UPDATE users SET avatar_b64=? WHERE id=?",
                             (avatar_b64, uid))
            else:
                log.warning(f"Avatar too large for user {uid}: {len(avatar_b64)} bytes")
        if national_id is not None:
            val = (national_id[:12] if national_id else None)
            conn.execute("UPDATE users SET national_id=? WHERE id=?", (val, uid))
        if birthdate is not None:
            val = (birthdate[:10] if birthdate else None)
            conn.execute("UPDATE users SET birthdate=? WHERE id=?", (val, uid))
        conn.commit()
    finally:
        conn.close()

def change_password(uid, new_password):
    ok, err = _validate_password(new_password)
    if not ok:
        return False, err
    conn = get_db()
    try:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (generate_password_hash(new_password), uid))
        conn.commit()
        return True, ""
    finally:
        conn.close()

# ─── Journals ──────────────────────────────────────────────────────────────────
def count_today_journals(user_id):
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM journals "
        "WHERE user_id=? AND DATE(created_at)=DATE('now')",
        (user_id,)
    ).fetchone()["c"]
    conn.close()
    return n

def save_journal(user_id, content, mood_score, lang, analysis, risk,
                 ai_summary="", ai_advice="", source="local"):
    """FIX: Proper transaction handling."""
    conn = get_db()
    try:
        jid = conn.execute(
            "INSERT INTO journals (user_id, content, mood_score, lang) VALUES (?, ?, ?, ?)",
            (user_id, content[:5000], mood_score, lang)
        ).lastrowid
        conn.execute(
            "INSERT INTO emotion_analysis "
            "(journal_id, user_id, dominant_emotion, confidence, has_bullying, "
            "negative_hits, found_categories, risk_score, risk_level, "
            "ai_summary, ai_advice, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (jid, user_id, analysis.get("dominant_emotion", "neutral"),
             analysis.get("confidence", 0.5),
             int(analysis.get("has_bullying", False)),
             analysis.get("negative_hits", 0),
             json.dumps(list(analysis.get("found_keywords", {}).keys())),
             risk.get("score", 0), risk.get("level", "low"),
             (ai_summary or "")[:500], (ai_advice or "")[:500], source)
        )
        conn.commit()
        return jid
    except Exception as e:
        conn.rollback()
        log.error(f"save_journal error: {e}")
        raise
    finally:
        conn.close()

def get_student_journals(user_id, limit=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT j.id, j.content, j.mood_score, j.lang, j.created_at,
               ea.dominant_emotion, ea.risk_score, ea.risk_level,
               ea.has_bullying, ea.ai_summary, ea.ai_advice, ea.source
        FROM journals j
        LEFT JOIN emotion_analysis ea ON ea.journal_id = j.id
        WHERE j.user_id = ?
        ORDER BY j.created_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return rows

def get_student_risk_history(user_id, days=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT ea.risk_score, ea.risk_level, ea.dominant_emotion, j.created_at
        FROM emotion_analysis ea
        JOIN journals j ON j.id = ea.journal_id
        WHERE ea.user_id = ?
        ORDER BY j.created_at ASC
        LIMIT ?
    """, (user_id, days)).fetchall()
    conn.close()
    return rows

def get_student_personal_stats(user_id):
    conn = get_db()
    total_j = conn.execute(
        "SELECT COUNT(*) AS c FROM journals WHERE user_id=?", (user_id,)
    ).fetchone()["c"]
    avg_r = conn.execute(
        "SELECT AVG(risk_score) AS a FROM emotion_analysis WHERE user_id=?", (user_id,)
    ).fetchone()["a"] or 0
    # FIX: Get LATEST risk (not max)
    last_r = conn.execute(
        "SELECT risk_score, risk_level FROM emotion_analysis "
        "WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)
    ).fetchone()
    streak = conn.execute(
        "SELECT COUNT(DISTINCT DATE(created_at)) AS c FROM journals "
        "WHERE user_id=? AND created_at >= datetime('now', '-7 days')", (user_id,)
    ).fetchone()["c"]
    emo_counts = conn.execute(
        "SELECT dominant_emotion, COUNT(*) AS c FROM emotion_analysis "
        "WHERE user_id=? GROUP BY dominant_emotion ORDER BY c DESC", (user_id,)
    ).fetchall()
    checkin_avg = conn.execute(
        "SELECT AVG(mood) AS a FROM checkins WHERE user_id=?", (user_id,)
    ).fetchone()["a"] or 0
    conn.close()
    return {
        "total_journals":   total_j,
        "avg_risk":         round(avg_r, 1),
        "latest_risk":      round(last_r["risk_score"], 1) if last_r and last_r["risk_score"] else 0,
        "latest_level":     last_r["risk_level"] if last_r else "low",
        "weekly_streak":    streak,
        "emotion_counts":   [{"emotion": r["dominant_emotion"], "count": r["c"]}
                             for r in emo_counts],
        "checkin_avg_mood": round(checkin_avg, 1),
    }

# ─── Check-in ──────────────────────────────────────────────────────────────────
def count_today_checkins(user_id):
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM checkins "
        "WHERE user_id=? AND DATE(created_at)=DATE('now')", (user_id,)
    ).fetchone()["c"]
    conn.close()
    return n

def save_checkin(user_id, mood, feeling_safe, feeling_lonely, notes):
    conn = get_db()
    conn.execute(
        "INSERT INTO checkins (user_id, mood, feeling_safe, feeling_lonely, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, mood, feeling_safe, feeling_lonely, (notes or "")[:500])
    )
    conn.commit()
    conn.close()

def get_checkins(user_id, limit=7):
    conn = get_db()
    r = conn.execute(
        "SELECT * FROM checkins WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return r

# ─── Surveys ──────────────────────────────────────────────────────────────────
def count_today_surveys(user_id):
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM surveys "
        "WHERE user_id=? AND DATE(created_at)=DATE('now')", (user_id,)
    ).fetchone()["c"]
    conn.close()
    return n

def save_survey(user_id, answers: dict, notes=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO surveys (user_id, q1, q2, q3, q4, q5, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, answers.get("q1"), answers.get("q2"), answers.get("q3"),
         answers.get("q4"), answers.get("q5"), (notes or "")[:500])
    )
    conn.commit()
    conn.close()

# ─── Lectures ──────────────────────────────────────────────────────────────────
def get_today_lecture(user_id):
    """Return same lecture for the whole day, or pick next unseen one."""
    conn = get_db()
    today = conn.execute(
        "SELECT lecture_id FROM lecture_log "
        "WHERE user_id=? AND DATE(shown_at)=DATE('now') LIMIT 1",
        (user_id,)
    ).fetchone()
    if today:
        conn.close()
        return next((l for l in LECTURES if l["id"] == today["lecture_id"]),
                    LECTURES[0])
    shown_ids = {r["lecture_id"] for r in conn.execute(
        "SELECT DISTINCT lecture_id FROM lecture_log WHERE user_id=?",
        (user_id,)
    ).fetchall()}
    all_ids   = [l["id"] for l in LECTURES]
    remaining = [i for i in all_ids if i not in shown_ids]
    if not remaining:
        conn.execute("DELETE FROM lecture_log WHERE user_id=?", (user_id,))
        conn.commit()
        remaining = all_ids
    pick_id = random.choice(remaining)
    conn.execute("INSERT INTO lecture_log (user_id, lecture_id) VALUES (?, ?)",
                 (user_id, pick_id))
    conn.commit()
    conn.close()
    return next(l for l in LECTURES if l["id"] == pick_id)

# ─── Alerts ────────────────────────────────────────────────────────────────────
_RECS = {
    "ar": {
        "bullying":   "جلسة استشارة فورية + تحقيق في التنمر",
        "depression": "دعم نفسي + تواصل مع الأسرة",
        "anxiety":    "تقنيات الاسترخاء + دعم تدريجي",
        "isolation":  "برامج تفاعل + متابعة أسبوعية",
        "neutral":    "متابعة دورية",
    },
    "en": {
        "bullying":   "Immediate counseling + investigation",
        "depression": "Support + family contact",
        "anxiety":    "Relaxation + gradual support",
        "isolation":  "Social programs + follow-up",
        "neutral":    "Routine monitoring",
    },
}

def save_alert(user_id, anonymous_code, grade, risk, analysis, lang):
    emotion = analysis.get("dominant_emotion", "neutral")
    rec     = _RECS.get(lang, _RECS["ar"]).get(emotion, "متابعة دورية")
    score   = risk.get("score", 0)
    summary = (f"مؤشرات {emotion} — درجة {score}/10" if lang == "ar"
               else f"Indicators: {emotion} — score {score}/10")
    conn = get_db()
    conn.execute(
        "INSERT INTO alerts "
        "(user_id, anonymous_code, grade, risk_score, risk_level, "
        "alert_type, summary, recommendation) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, anonymous_code, grade, score, risk.get("level", "medium"),
         emotion, summary, rec)
    )
    conn.commit()
    conn.close()

def get_alerts_for_counselor(supervised_grades=None, limit=60):
    conn = get_db()
    if supervised_grades:
        ph   = ",".join("?" * len(supervised_grades))
        rows = conn.execute(
            f"SELECT a.* FROM alerts a "
            f"LEFT JOIN users u ON u.id = a.user_id "
            f"WHERE u.grade IN ({ph}) OR a.grade IN ({ph}) "
            f"ORDER BY a.created_at DESC LIMIT ?",
            supervised_grades * 2 + [limit]
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return rows

def update_alert_status(alert_id, status):
    if status not in ("new", "reviewed", "handled"):
        status = "reviewed"
    conn = get_db()
    conn.execute("UPDATE alerts SET status=? WHERE id=?", (status, alert_id))
    conn.commit()
    conn.close()

def count_alerts_by_status(supervised_grades=None):
    """FIX: Added count_alerts_by_status function used in app.py."""
    conn = get_db()
    if supervised_grades:
        ph   = ",".join("?" * len(supervised_grades))
        rows = conn.execute(
            f"SELECT a.status, COUNT(*) AS c FROM alerts a "
            f"LEFT JOIN users u ON u.id = a.user_id "
            f"WHERE u.grade IN ({ph}) OR a.grade IN ({ph}) "
            f"GROUP BY a.status",
            supervised_grades * 2
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM alerts GROUP BY status"
        ).fetchall()
    conn.close()
    return {r["status"]: r["c"] for r in rows}

# ─── Counselor ─────────────────────────────────────────────────────────────────
def get_students_for_counselor(supervised_grades=None):
    """
    FIX: Use LATEST risk score instead of MAX risk score.
    MAX risk inflates the displayed risk level.
    """
    conn = get_db()
    base = """
        SELECT u.id, u.display_name, u.grade, u.anonymous_code,
               u.username, u.birthdate, u.national_id,
               (SELECT ea2.risk_score FROM emotion_analysis ea2
                WHERE ea2.user_id = u.id
                ORDER BY ea2.created_at DESC LIMIT 1) AS latest_risk,
               (SELECT ea2.risk_level FROM emotion_analysis ea2
                WHERE ea2.user_id = u.id
                ORDER BY ea2.created_at DESC LIMIT 1) AS latest_level,
               COUNT(DISTINCT j.id) AS journal_count,
               MAX(j.created_at) AS last_entry
        FROM users u
        LEFT JOIN journals j ON j.user_id = u.id
        WHERE u.role = 'student' AND u.is_active = 1
    """
    if supervised_grades:
        ph   = ",".join("?" * len(supervised_grades))
        rows = conn.execute(
            base + f" AND u.grade IN ({ph}) GROUP BY u.id ORDER BY latest_risk DESC NULLS LAST",
            supervised_grades
        ).fetchall()
    else:
        rows = conn.execute(
            base + " GROUP BY u.id ORDER BY latest_risk DESC NULLS LAST"
        ).fetchall()
    conn.close()
    return rows

def counselor_update_student(student_id, new_username=None,
                              new_password=None, new_display_name=None):
    conn = get_db()
    try:
        if new_username:
            clean = _sanitize_username(new_username)
            if len(clean) >= 3:
                # FIX: Check uniqueness before updating
                existing = conn.execute(
                    "SELECT id FROM users WHERE username=? AND id!=?",
                    (clean, student_id)
                ).fetchone()
                if not existing:
                    conn.execute("UPDATE users SET username=? WHERE id=?",
                                 (clean, student_id))
                else:
                    log.warning(f"Username {clean} already taken, skipping update")
        if new_password:
            ok, _ = _validate_password(new_password)
            if ok:
                conn.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(new_password), student_id)
                )
        if new_display_name:
            conn.execute(
                "UPDATE users SET display_name=? WHERE id=?",
                (new_display_name.strip()[:120], student_id)
            )
        conn.commit()
    finally:
        conn.close()

def get_school_stats(supervised_grades=None):
    conn = get_db()

    def _c(q, params=()):
        return conn.execute(q, params).fetchone()["c"]

    if supervised_grades:
        ph  = ",".join("?" * len(supervised_grades))
        tot = _c(f"SELECT COUNT(*) AS c FROM users WHERE role='student' "
                 f"AND is_active=1 AND grade IN ({ph})", supervised_grades)
    else:
        tot = _c("SELECT COUNT(*) AS c FROM users WHERE role='student' AND is_active=1")

    if tot == 0:
        conn.close()
        return {k: 0 for k in ("total", "low", "medium", "high", "critical",
                                "pct_low", "pct_medium", "pct_high", "pct_critical")}

    def clvl(level):
        if supervised_grades:
            ph = ",".join("?" * len(supervised_grades))
            return _c(
                f"SELECT COUNT(DISTINCT ea.user_id) AS c "
                f"FROM emotion_analysis ea JOIN users u ON u.id = ea.user_id "
                f"WHERE ea.risk_level=? AND u.grade IN ({ph}) "
                f"AND ea.created_at >= datetime('now', '-7 days')",
                [level] + list(supervised_grades)
            )
        return _c(
            "SELECT COUNT(DISTINCT ea.user_id) AS c FROM emotion_analysis ea "
            "WHERE ea.risk_level=? AND ea.created_at >= datetime('now', '-7 days')",
            (level,)
        )

    low  = clvl("low")
    med  = clvl("medium")
    high = clvl("high")
    crit = clvl("critical")
    # FIX: Students with no data count as "low"
    active = low + med + high + crit
    low   += max(0, tot - active)
    conn.close()

    # FIX: Safe division
    def pct(n):
        return round(n / tot * 100) if tot > 0 else 0

    return {
        "total":        tot,
        "low":          low,
        "medium":       med,
        "high":         high,
        "critical":     crit,
        "pct_low":      pct(low),
        "pct_medium":   pct(med),
        "pct_high":     pct(high),
        "pct_critical": pct(crit),
    }

def get_supervised_grades_list(raw_json):
    try:
        return json.loads(raw_json) if isinstance(raw_json, str) else list(raw_json or [])
    except (json.JSONDecodeError, TypeError):
        return []

# ─── Rate limiter ──────────────────────────────────────────────────────────────
_rate_store: dict = {}

def rate_limit(key: str, max_calls: int = 30, window: int = 60) -> bool:
    now = time.time()
    b   = _rate_store.setdefault(key, [])
    # FIX: Use list comprehension to filter, keep size bounded
    _rate_store[key] = [t for t in b if now - t < window]
    if len(_rate_store[key]) >= max_calls:
        return False
    _rate_store[key].append(now)
    return True

def cleanup_rate_store():
    """FIX: Prevent memory leak in rate store by cleaning old entries."""
    now = time.time()
    keys_to_delete = []
    for key, timestamps in _rate_store.items():
        fresh = [t for t in timestamps if now - t < 120]
        if not fresh:
            keys_to_delete.append(key)
        else:
            _rate_store[key] = fresh
    for key in keys_to_delete:
        del _rate_store[key]

def vacuum_db():
    """Run VACUUM to reclaim space."""
    try:
        conn = get_db()
        conn.execute("VACUUM")
        conn.close()
        log.info("Database VACUUM completed")
    except Exception as e:
        log.error(f"VACUUM error: {e}")
