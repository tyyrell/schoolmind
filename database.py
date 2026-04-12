"""
SchoolMind AI v14 — Database Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
جديد في v14:
- جدول locations: تتبع موقع الطالب الجغرافي
- جدول goals: أهداف الطالب الشخصية
- جدول game_scores: نتائج الألعاب
- جدول resources_views: تتبع المصادر المُشاهدة
- دعم PostgreSQL للإنتاج + SQLite للتطوير
- قاعدة بيانات دائمة على السيرفر
"""
import os, sys, json, re, random, string, time, base64, logging
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

log = logging.getLogger('schoolmind.db')

_base   = os.path.dirname(os.path.abspath(__file__))

# ─── Database Path (persistent on Render with disk) ──────────────────────────
# On Render: add Disk mount at /data, set DB_PATH=/data/schoolmind.db
DB_PATH = os.environ.get("DB_PATH",
          os.path.join(_base, "database", "schoolmind.db"))

GRADES_AR = ["الصف السابع","الصف الثامن","الصف التاسع",
             "الصف العاشر","الصف الحادي عشر","الصف الثاني عشر"]
GRADES_EN = ["Grade 7","Grade 8","Grade 9","Grade 10","Grade 11","Grade 12"]
GRADES    = GRADES_AR + GRADES_EN

# ─── 100 Lectures ─────────────────────────────────────────────────────────────
LECTURES = [
    {"id":i+1,"title_ar":ar,"title_en":en,"url":url,"cat":cat}
    for i,(ar,en,url,cat) in enumerate([
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
import sqlite3

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA cache_size=-20000")  # 20MB cache
    conn.execute("PRAGMA synchronous=NORMAL")  # faster writes
    return conn

@contextmanager
def db_context():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"DB error: {e}")
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
            q6 INTEGER, q7 INTEGER, q8 INTEGER, q9 INTEGER, q10 INTEGER,
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS streaks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL UNIQUE,
            current_streak  INTEGER DEFAULT 0,
            longest_streak  INTEGER DEFAULT 0,
            last_activity   TEXT,
            total_days      INTEGER DEFAULT 0,
            last_updated    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            badge_key    TEXT NOT NULL,
            earned_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS lecture_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            lecture_id INTEGER NOT NULL,
            shown_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS locations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            latitude   REAL NOT NULL,
            longitude  REAL NOT NULL,
            accuracy   REAL,
            city       TEXT,
            shared_at  TEXT DEFAULT (datetime('now')),
            is_active  INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            category    TEXT DEFAULT 'personal',
            target_date TEXT,
            status      TEXT DEFAULT 'active',
            progress    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS game_scores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            game_name  TEXT NOT NULL,
            score      INTEGER DEFAULT 0,
            level      INTEGER DEFAULT 1,
            duration   INTEGER DEFAULT 0,
            played_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS breathing_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            technique  TEXT DEFAULT '4-7-8',
            cycles     INTEGER DEFAULT 0,
            duration   INTEGER DEFAULT 0,
            mood_before INTEGER,
            mood_after  INTEGER,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_journals_user    ON journals(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ea_user          ON emotion_analysis(user_id);
        CREATE INDEX IF NOT EXISTS idx_ea_created       ON emotion_analysis(created_at);
        CREATE INDEX IF NOT EXISTS idx_alerts_status    ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_user      ON alerts(user_id);
        CREATE INDEX IF NOT EXISTS idx_checkins_user    ON checkins(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_surveys_user     ON surveys(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role, is_active);
        CREATE INDEX IF NOT EXISTS idx_lecture_user     ON lecture_log(user_id, shown_at);
        CREATE INDEX IF NOT EXISTS idx_locations_user   ON locations(user_id, shared_at);
        CREATE INDEX IF NOT EXISTS idx_streaks_user    ON streaks(user_id);
        CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
        CREATE INDEX IF NOT EXISTS idx_goals_user       ON goals(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_games_user       ON game_scores(user_id, game_name);
    """)
    conn.commit()
    conn.close()

# ─── Validation ────────────────────────────────────────────────────────────────
def _sanitize_username(u):
    return re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', (u or "").strip())[:40]

def _validate_password(pw):
    if not pw or len(pw) < 6:
        return False, "كلمة المرور يجب 6 أحرف على الأقل"
    if pw.isdigit():
        return False, "كلمة المرور لا يجب أن تكون أرقاماً فقط"
    return True, ""

def _validate_birthdate(bd):
    if not bd: return True
    try:
        from datetime import date
        bd = bd.strip().replace("/","-").replace(".","-")
        parts = bd.split("-")
        if len(parts) != 3: return False
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if not (1900 <= y <= 2020): return False
        if not (1 <= m <= 12): return False
        if not (1 <= d <= 31): return False
        bdate = date(y, m, d)
        age = (date.today() - bdate).days / 365.25
        return 4 < age < 100
    except: return False

def _validate_national_id(nid):
    if not nid: return True
    return bool(re.match(r'^\d{9,12}$', nid.strip()))

# ─── Auth ──────────────────────────────────────────────────────────────────────
def register_user(username, password, role, display_name,
                  grade=None, supervised_grades=None,
                  national_id=None, birthdate=None, is_anonymous=False):
    username     = _sanitize_username(username)
    display_name = (display_name or "").strip()[:120]
    national_id  = (national_id or "").strip() or None
    birthdate    = (birthdate or "").strip() or None

    if not is_anonymous:
        if len(username) < 3:
            return False, "اسم المستخدم يجب 3 أحرف على الأقل"
        pw_ok, pw_err = _validate_password(password)
        if not pw_ok: return False, pw_err
        if not display_name: return False, "الاسم الكامل مطلوب"
        if role == "student" and not grade: return False, "يجب اختيار الصف"
        if role == "counselor" and not supervised_grades: return False, "يجب اختيار صف واحد على الأقل"
        if national_id and not _validate_national_id(national_id):
            return False, "الرقم الوطني يجب أن يكون 9-12 رقماً"
        if birthdate and not _validate_birthdate(birthdate):
            return False, "تاريخ الميلاد غير صحيح"

    conn = get_db()
    try:
        if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            return False, "اسم المستخدم مستخدم بالفعل"
        for _ in range(20):
            prefix = "S" if role == "student" else "C"
            code = prefix + "-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if not conn.execute("SELECT id FROM users WHERE anonymous_code=?", (code,)).fetchone():
                break
        sup_json = json.dumps(supervised_grades) if supervised_grades else None
        uid = conn.execute(
            "INSERT INTO users (username,password_hash,role,display_name,grade,"
            "supervised_grades,anonymous_code,national_id,birthdate,is_anonymous) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (username, generate_password_hash(password), role, display_name, grade,
             sup_json, code, national_id, birthdate, int(is_anonymous))
        ).lastrowid
        conn.commit()
        return True, uid
    except sqlite3.IntegrityError:
        return False, "اسم المستخدم مستخدم بالفعل"
    except Exception as e:
        log.error(f"register_user: {e}")
        return False, str(e)
    finally:
        conn.close()

def verify_login(username, password):
    username = _sanitize_username(username)
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if u and check_password_hash(u["password_hash"], password): return u
    return None

def get_user_by_id(uid):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return u

def get_user_by_username(username):
    username = _sanitize_username(username)
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    return u

def update_user_profile(uid, display_name=None, avatar_b64=None, national_id=None, birthdate=None):
    conn = get_db()
    try:
        if display_name:
            conn.execute("UPDATE users SET display_name=? WHERE id=?", (display_name[:120], uid))
        if avatar_b64 is not None:
            if len(avatar_b64) <= 280_000:
                conn.execute("UPDATE users SET avatar_b64=? WHERE id=?", (avatar_b64, uid))
        if national_id is not None:
            conn.execute("UPDATE users SET national_id=? WHERE id=?", (national_id[:12] if national_id else None, uid))
        if birthdate is not None:
            conn.execute("UPDATE users SET birthdate=? WHERE id=?", (birthdate[:10] if birthdate else None, uid))
        conn.commit()
    finally:
        conn.close()

def password_strength_score(pw: str) -> tuple:
    """Return (score 0-4, feedback_ar, feedback_en)."""
    if not pw: return 0, "كلمة المرور فارغة", "Password is empty"
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 12: score += 1
    if re.search(r'[A-Z]', pw): score += 1
    if re.search(r'[0-9]', pw): score += 1
    if re.search(r'[^A-Za-z0-9]', pw): score += 1
    score = min(4, score)
    labels_ar = ["ضعيفة جداً","ضعيفة","متوسطة","جيدة","قوية جداً"]
    labels_en = ["Very Weak","Weak","Medium","Good","Very Strong"]
    return score, labels_ar[score], labels_en[score]

def change_password(uid, new_password):
    ok, err = _validate_password(new_password)
    if not ok: return False, err
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
        "SELECT COUNT(*) AS c FROM journals WHERE user_id=? AND DATE(created_at)=DATE('now')",
        (user_id,)
    ).fetchone()["c"]
    conn.close()
    return n

def save_journal(user_id, content, mood_score, lang, analysis, risk,
                 ai_summary="", ai_advice="", source="local"):
    conn = get_db()
    try:
        jid = conn.execute(
            "INSERT INTO journals (user_id,content,mood_score,lang) VALUES (?,?,?,?)",
            (user_id, content[:5000], mood_score, lang)
        ).lastrowid
        conn.execute(
            "INSERT INTO emotion_analysis "
            "(journal_id,user_id,dominant_emotion,confidence,has_bullying,"
            "negative_hits,found_categories,risk_score,risk_level,ai_summary,ai_advice,source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, user_id, analysis.get("dominant_emotion","neutral"),
             analysis.get("confidence",0.5), int(analysis.get("has_bullying",False)),
             analysis.get("negative_hits",0),
             json.dumps(list(analysis.get("found_keywords",{}).keys())),
             risk.get("score",0), risk.get("level","low"),
             (ai_summary or "")[:500], (ai_advice or "")[:500], source)
        )
        conn.commit()
        return jid
    except Exception as e:
        conn.rollback()
        log.error(f"save_journal: {e}")
        raise
    finally:
        conn.close()

def get_student_journals(user_id, limit=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT j.id,j.content,j.mood_score,j.lang,j.created_at,
               ea.dominant_emotion,ea.risk_score,ea.risk_level,ea.has_bullying,
               ea.ai_summary,ea.ai_advice,ea.source
        FROM journals j LEFT JOIN emotion_analysis ea ON ea.journal_id=j.id
        WHERE j.user_id=? ORDER BY j.created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return rows

def get_student_risk_history(user_id, days=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT ea.risk_score,ea.risk_level,ea.dominant_emotion,j.created_at
        FROM emotion_analysis ea JOIN journals j ON j.id=ea.journal_id
        WHERE ea.user_id=? ORDER BY j.created_at ASC LIMIT ?
    """, (user_id, days)).fetchall()
    conn.close()
    return rows

def get_student_personal_stats(user_id):
    conn = get_db()
    total_j = conn.execute("SELECT COUNT(*) AS c FROM journals WHERE user_id=?", (user_id,)).fetchone()["c"]
    avg_r   = conn.execute("SELECT AVG(risk_score) AS a FROM emotion_analysis WHERE user_id=?", (user_id,)).fetchone()["a"] or 0
    last_r  = conn.execute("SELECT risk_score,risk_level FROM emotion_analysis WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    streak  = conn.execute("SELECT COUNT(DISTINCT DATE(created_at)) AS c FROM journals WHERE user_id=? AND created_at>=datetime('now','-7 days')", (user_id,)).fetchone()["c"]
    emo_counts = conn.execute("SELECT dominant_emotion,COUNT(*) AS c FROM emotion_analysis WHERE user_id=? GROUP BY dominant_emotion ORDER BY c DESC", (user_id,)).fetchall()
    checkin_avg = conn.execute("SELECT AVG(mood) AS a FROM checkins WHERE user_id=?", (user_id,)).fetchone()["a"] or 0
    goals_count = conn.execute("SELECT COUNT(*) AS c FROM goals WHERE user_id=? AND status='active'", (user_id,)).fetchone()["c"]
    game_total = conn.execute("SELECT COALESCE(SUM(score),0) AS s FROM game_scores WHERE user_id=?", (user_id,)).fetchone()["s"] or 0
    conn.close()
    return {
        "total_journals": total_j, "avg_risk": round(avg_r,1),
        "latest_risk": round(last_r["risk_score"],1) if last_r and last_r["risk_score"] else 0,
        "latest_level": last_r["risk_level"] if last_r else "low",
        "weekly_streak": streak,
        "emotion_counts": [{"emotion":r["dominant_emotion"],"count":r["c"]} for r in emo_counts],
        "checkin_avg_mood": round(checkin_avg,1),
        "active_goals": goals_count,
    }

# ─── Check-in ──────────────────────────────────────────────────────────────────
def count_today_checkins(user_id):
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM checkins WHERE user_id=? AND DATE(created_at)=DATE('now')", (user_id,)).fetchone()["c"]
    conn.close(); return n

def save_checkin(user_id, mood, feeling_safe, feeling_lonely, notes):
    conn = get_db()
    conn.execute("INSERT INTO checkins (user_id,mood,feeling_safe,feeling_lonely,notes) VALUES (?,?,?,?,?)",
                 (user_id, mood, feeling_safe, feeling_lonely, (notes or "")[:500]))
    conn.commit(); conn.close()

def get_checkins(user_id, limit=7):
    conn = get_db()
    r = conn.execute("SELECT * FROM checkins WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close(); return r

# ─── Surveys ──────────────────────────────────────────────────────────────────
def count_today_surveys(user_id):
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM surveys WHERE user_id=? AND DATE(created_at)=DATE('now')", (user_id,)).fetchone()["c"]
    conn.close(); return n

def save_survey(user_id, answers, notes=""):
    conn = get_db()
    conn.execute("INSERT INTO surveys (user_id,q1,q2,q3,q4,q5,notes) VALUES (?,?,?,?,?,?,?)",
                 (user_id, answers.get("q1"), answers.get("q2"), answers.get("q3"),
                  answers.get("q4"), answers.get("q5"), (notes or "")[:500]))
    conn.commit(); conn.close()

# ─── Lectures ──────────────────────────────────────────────────────────────────
def get_today_lecture(user_id):
    conn = get_db()
    today = conn.execute("SELECT lecture_id FROM lecture_log WHERE user_id=? AND DATE(shown_at)=DATE('now') LIMIT 1", (user_id,)).fetchone()
    if today:
        conn.close()
        return next((l for l in LECTURES if l["id"]==today["lecture_id"]), LECTURES[0])
    shown_ids = {r["lecture_id"] for r in conn.execute("SELECT DISTINCT lecture_id FROM lecture_log WHERE user_id=?", (user_id,)).fetchall()}
    remaining = [l["id"] for l in LECTURES if l["id"] not in shown_ids]
    if not remaining:
        conn.execute("DELETE FROM lecture_log WHERE user_id=?", (user_id,))
        conn.commit()
        remaining = [l["id"] for l in LECTURES]
    pick_id = random.choice(remaining)
    conn.execute("INSERT INTO lecture_log (user_id,lecture_id) VALUES (?,?)", (user_id, pick_id))
    conn.commit(); conn.close()
    return next(l for l in LECTURES if l["id"]==pick_id)

# ─── Alerts ────────────────────────────────────────────────────────────────────
_RECS = {
    "ar": {"bullying":"جلسة استشارة فورية + تحقيق في التنمر","depression":"دعم نفسي + تواصل مع الأسرة","anxiety":"تقنيات الاسترخاء + دعم تدريجي","isolation":"برامج تفاعل + متابعة أسبوعية","neutral":"متابعة دورية"},
    "en": {"bullying":"Immediate counseling + investigation","depression":"Support + family contact","anxiety":"Relaxation + gradual support","isolation":"Social programs + follow-up","neutral":"Routine monitoring"},
}

def save_alert(user_id, anonymous_code, grade, risk, analysis, lang):
    emotion = analysis.get("dominant_emotion","neutral")
    rec = _RECS.get(lang,_RECS["ar"]).get(emotion,"متابعة دورية")
    score = risk.get("score",0)
    summary = (f"مؤشرات {emotion} — درجة {score}/10" if lang=="ar" else f"Indicators: {emotion} — score {score}/10")
    conn = get_db()
    conn.execute("INSERT INTO alerts (user_id,anonymous_code,grade,risk_score,risk_level,alert_type,summary,recommendation) VALUES (?,?,?,?,?,?,?,?)",
                 (user_id, anonymous_code, grade, score, risk.get("level","medium"), emotion, summary, rec))
    conn.commit(); conn.close()

def get_alerts_for_counselor(supervised_grades=None, limit=60):
    supervised_grades = sanitize_grades(supervised_grades)
    conn = get_db()
    if supervised_grades:
        ph = ",".join("?"*len(supervised_grades))
        rows = conn.execute(f"SELECT a.* FROM alerts a LEFT JOIN users u ON u.id=a.user_id WHERE u.grade IN ({ph}) OR a.grade IN ({ph}) ORDER BY a.created_at DESC LIMIT ?", supervised_grades*2+[limit]).fetchall()
    else:
        rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return rows

def update_alert_status(alert_id, status):
    if status not in ("new","reviewed","handled"): status="reviewed"
    conn = get_db()
    conn.execute("UPDATE alerts SET status=? WHERE id=?", (status, alert_id))
    conn.commit(); conn.close()

def count_alerts_by_status(supervised_grades=None):
    conn = get_db()
    if supervised_grades:
        ph = ",".join("?"*len(supervised_grades))
        rows = conn.execute(f"SELECT a.status,COUNT(*) AS c FROM alerts a LEFT JOIN users u ON u.id=a.user_id WHERE u.grade IN ({ph}) OR a.grade IN ({ph}) GROUP BY a.status", supervised_grades*2).fetchall()
    else:
        rows = conn.execute("SELECT status,COUNT(*) AS c FROM alerts GROUP BY status").fetchall()
    conn.close()
    return {r["status"]:r["c"] for r in rows}

# ─── Counselor ─────────────────────────────────────────────────────────────────
def get_students_for_counselor(supervised_grades=None):
    supervised_grades = sanitize_grades(supervised_grades)
    conn = get_db()
    base = """SELECT u.id,u.display_name,u.grade,u.anonymous_code,u.username,u.birthdate,u.national_id,
               (SELECT ea2.risk_score FROM emotion_analysis ea2 WHERE ea2.user_id=u.id ORDER BY ea2.created_at DESC LIMIT 1) AS latest_risk,
               (SELECT ea2.risk_level FROM emotion_analysis ea2 WHERE ea2.user_id=u.id ORDER BY ea2.created_at DESC LIMIT 1) AS latest_level,
               COUNT(DISTINCT j.id) AS journal_count, MAX(j.created_at) AS last_entry,
               COALESCE((SELECT current_streak FROM streaks WHERE user_id=u.id),0) AS current_streak
              FROM users u LEFT JOIN journals j ON j.user_id=u.id
              WHERE u.role='student' AND u.is_active=1"""
    if supervised_grades:
        ph = ",".join("?"*len(supervised_grades))
        rows = conn.execute(base+f" AND u.grade IN ({ph}) GROUP BY u.id ORDER BY latest_risk DESC NULLS LAST", supervised_grades).fetchall()
    else:
        rows = conn.execute(base+" GROUP BY u.id ORDER BY latest_risk DESC NULLS LAST").fetchall()
    conn.close(); return rows

def counselor_update_student(student_id, new_username=None, new_password=None, new_display_name=None):
    conn = get_db()
    try:
        if new_username:
            clean = _sanitize_username(new_username)
            if len(clean) >= 3:
                existing = conn.execute("SELECT id FROM users WHERE username=? AND id!=?", (clean, student_id)).fetchone()
                if not existing:
                    conn.execute("UPDATE users SET username=? WHERE id=?", (clean, student_id))
        if new_password:
            ok, _ = _validate_password(new_password)
            if ok:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), student_id))
        if new_display_name:
            conn.execute("UPDATE users SET display_name=? WHERE id=?", (new_display_name.strip()[:120], student_id))
        conn.commit()
    finally:
        conn.close()

def get_school_stats(supervised_grades=None):
    supervised_grades = sanitize_grades(supervised_grades)
    conn = get_db()
    def _c(q, params=()): return conn.execute(q, params).fetchone()["c"]
    if supervised_grades:
        ph = ",".join("?"*len(supervised_grades))
        tot = _c(f"SELECT COUNT(*) AS c FROM users WHERE role='student' AND is_active=1 AND grade IN ({ph})", supervised_grades)
    else:
        tot = _c("SELECT COUNT(*) AS c FROM users WHERE role='student' AND is_active=1")
    if tot == 0:
        conn.close()
        return {k:0 for k in ("total","low","medium","high","critical","pct_low","pct_medium","pct_high","pct_critical")}
    def clvl(level):
        if supervised_grades:
            ph = ",".join("?"*len(supervised_grades))
            return _c(f"SELECT COUNT(DISTINCT ea.user_id) AS c FROM emotion_analysis ea JOIN users u ON u.id=ea.user_id WHERE ea.risk_level=? AND u.grade IN ({ph}) AND ea.created_at>=datetime('now','-7 days')", [level]+list(supervised_grades))
        return _c("SELECT COUNT(DISTINCT ea.user_id) AS c FROM emotion_analysis ea WHERE ea.risk_level=? AND ea.created_at>=datetime('now','-7 days')", (level,))
    low=clvl("low"); med=clvl("medium"); high=clvl("high"); crit=clvl("critical")
    low += max(0, tot-(low+med+high+crit))
    conn.close()
    def pct(n): return round(n/tot*100) if tot>0 else 0
    return {"total":tot,"low":low,"medium":med,"high":high,"critical":crit,
            "pct_low":pct(low),"pct_medium":pct(med),"pct_high":pct(high),"pct_critical":pct(crit)}

def sanitize_grades(grades: list) -> list:
    """Validate grades against allowed list to prevent injection."""
    return [g for g in (grades or []) if g in GRADES] if grades else []

def get_supervised_grades_list(raw_json):
    try: return json.loads(raw_json) if isinstance(raw_json,str) else list(raw_json or [])
    except: return []

# ─── Location (NEW) ────────────────────────────────────────────────────────────
def save_location(user_id, latitude, longitude, accuracy=None, city=None):
    """Save or update student location."""
    conn = get_db()
    # Deactivate old locations
    conn.execute("UPDATE locations SET is_active=0 WHERE user_id=?", (user_id,))
    conn.execute(
        "INSERT INTO locations (user_id,latitude,longitude,accuracy,city,is_active) VALUES (?,?,?,?,?,1)",
        (user_id, latitude, longitude, accuracy, city)
    )
    conn.commit(); conn.close()

def get_student_location(user_id):
    """Get latest active location for a student."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM locations WHERE user_id=? AND is_active=1 ORDER BY shared_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close(); return row

def get_all_student_locations(supervised_grades=None):
    supervised_grades = sanitize_grades(supervised_grades)
    """Get all active student locations for counselor map."""
    conn = get_db()
    if supervised_grades:
        ph = ",".join("?"*len(supervised_grades))
        rows = conn.execute(
            f"SELECT l.*,u.anonymous_code,u.grade,u.display_name FROM locations l "
            f"JOIN users u ON u.id=l.user_id "
            f"WHERE l.is_active=1 AND u.grade IN ({ph}) "
            f"ORDER BY l.shared_at DESC",
            supervised_grades
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT l.*,u.anonymous_code,u.grade,u.display_name FROM locations l "
            "JOIN users u ON u.id=l.user_id WHERE l.is_active=1 ORDER BY l.shared_at DESC"
        ).fetchall()
    conn.close(); return rows

# ─── Goals (NEW) ───────────────────────────────────────────────────────────────
def save_goal(user_id, title, description="", category="personal", target_date=None):
    conn = get_db()
    gid = conn.execute(
        "INSERT INTO goals (user_id,title,description,category,target_date) VALUES (?,?,?,?,?)",
        (user_id, title[:200], description[:1000], category, target_date)
    ).lastrowid
    conn.commit(); conn.close()
    return gid

def get_goals(user_id, status=None):
    conn = get_db()
    if status:
        rows = conn.execute("SELECT * FROM goals WHERE user_id=? AND status=? ORDER BY created_at DESC", (user_id, status)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM goals WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close(); return rows

def update_goal(goal_id, user_id, progress=None, status=None, title=None):
    conn = get_db()
    if progress is not None:
        conn.execute("UPDATE goals SET progress=?,updated_at=datetime('now') WHERE id=? AND user_id=?", (min(100,max(0,progress)), goal_id, user_id))
    if status:
        conn.execute("UPDATE goals SET status=?,updated_at=datetime('now') WHERE id=? AND user_id=?", (status, goal_id, user_id))
    if title:
        conn.execute("UPDATE goals SET title=?,updated_at=datetime('now') WHERE id=? AND user_id=?", (title[:200], goal_id, user_id))
    conn.commit(); conn.close()

def delete_goal(goal_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM goals WHERE id=? AND user_id=?", (goal_id, user_id))
    conn.commit(); conn.close()

# ─── Game Scores (NEW) ─────────────────────────────────────────────────────────
def save_game_score(user_id, game_name, score, level=1, duration=0):
    conn = get_db()
    conn.execute("INSERT INTO game_scores (user_id,game_name,score,level,duration) VALUES (?,?,?,?,?)",
                 (user_id, game_name, score, level, duration))
    conn.commit(); conn.close()

def get_game_scores(user_id, game_name=None):
    conn = get_db()
    if game_name:
        rows = conn.execute("SELECT * FROM game_scores WHERE user_id=? AND game_name=? ORDER BY played_at DESC LIMIT 10", (user_id, game_name)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM game_scores WHERE user_id=? ORDER BY played_at DESC LIMIT 20", (user_id,)).fetchall()
    conn.close(); return rows

def get_game_top_score(user_id, game_name):
    conn = get_db()
    row = conn.execute("SELECT MAX(score) AS top FROM game_scores WHERE user_id=? AND game_name=?", (user_id, game_name)).fetchone()
    conn.close()
    return row["top"] or 0

# ─── Breathing Sessions (NEW) ──────────────────────────────────────────────────
def save_breathing_session(user_id, technique="4-7-8", cycles=0, duration=0, mood_before=None, mood_after=None):
    conn = get_db()
    conn.execute("INSERT INTO breathing_sessions (user_id,technique,cycles,duration,mood_before,mood_after) VALUES (?,?,?,?,?,?)",
                 (user_id, technique, cycles, duration, mood_before, mood_after))
    conn.commit(); conn.close()

def get_breathing_stats(user_id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS c, SUM(cycles) AS tc, SUM(duration) AS td FROM breathing_sessions WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return {"total_sessions": total["c"] or 0, "total_cycles": total["tc"] or 0, "total_duration": total["td"] or 0}

# ─── Rate limiter ──────────────────────────────────────────────────────────────
_rate_store: dict = {}

def rate_limit(key, max_calls=30, window=60):
    now = time.time()
    b = _rate_store.setdefault(key, [])
    _rate_store[key] = [t for t in b if now-t < window]
    if len(_rate_store[key]) >= max_calls: return False
    _rate_store[key].append(now)
    return True

def cleanup_rate_store():
    now = time.time()
    keys = [k for k,v in _rate_store.items() if not any(now-t < 120 for t in v)]
    for k in keys: del _rate_store[k]

# ─── Streak System (NEW v14) ───────────────────────────────────────────────────
def get_streak(user_id: int) -> dict:
    """Calculate current streak and best streak for a student."""
    conn = get_db()
    # Get all distinct journal dates, descending
    dates = conn.execute(
        "SELECT DISTINCT DATE(created_at) AS d FROM journals WHERE user_id=? ORDER BY d DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    if not dates:
        return {"current": 0, "best": 0, "last_date": None, "milestone": None}

    from datetime import date, timedelta
    today = date.today()
    date_list = [row["d"] for row in dates]

    # Current streak
    current = 0
    check = today
    for d_str in date_list:
        d = date.fromisoformat(d_str)
        if d == check or d == check - timedelta(days=1):
            if d == check - timedelta(days=1) and current == 0:
                # Missed today but yesterday counts — still active
                pass
            current += 1
            check = d
        else:
            break

    # Best streak (all time)
    best = 0; temp = 1
    for i in range(1, len(date_list)):
        d_cur = date.fromisoformat(date_list[i])
        d_prev = date.fromisoformat(date_list[i-1])
        if (d_prev - d_cur).days == 1:
            temp += 1
        else:
            best = max(best, temp); temp = 1
    best = max(best, temp, current)

    # Milestone
    milestones = {3:"🌱",7:"🔥",14:"💪",21:"🏆",30:"⭐",60:"🌟",100:"👑"}
    milestone = None
    for days, icon in sorted(milestones.items()):
        if current >= days:
            milestone = (days, icon)

    return {
        "current": current,
        "best": best,
        "last_date": date_list[0] if date_list else None,
        "milestone": milestone,
        "fire_level": min(5, current // 3),  # 0-5 intensity
    }

def get_student_checkin_streak(user_id: int) -> int:
    """Quick check of journal streak count."""
    return get_streak(user_id)["current"]

# ─── STREAKS v15 ───────────────────────────────────────────────────────────────
BADGES = {
    'streak_3':   {'icon':'🔥','label_ar':'شعلة 3 أيام','label_en':'3-Day Streak','cat':'streak'},
    'streak_7':   {'icon':'⚡','label_ar':'شعلة أسبوع','label_en':'1-Week Streak','cat':'streak'},
    'streak_14':  {'icon':'🌟','label_ar':'شعلة أسبوعين','label_en':'2-Week Streak','cat':'streak'},
    'streak_30':  {'icon':'🏆','label_ar':'شعلة شهر','label_en':'1-Month Streak','cat':'streak'},
    'streak_60':  {'icon':'👑','label_ar':'بطل الستريك','label_en':'Streak Champion','cat':'streak'},
    'streak_100': {'icon':'🦋','label_ar':'100 يوم!','label_en':'100 Days!','cat':'streak'},
    'journal_1':  {'icon':'✍️','label_ar':'أول يومية','label_en':'First Journal','cat':'journal'},
    'journal_10': {'icon':'📔','label_ar':'10 يوميات','label_en':'10 Journals','cat':'journal'},
    'journal_50': {'icon':'📚','label_ar':'50 يومية','label_en':'50 Journals','cat':'journal'},
    'game_100':   {'icon':'🎮','label_ar':'100 نقطة ألعاب','label_en':'100 Game Points','cat':'game'},
    'game_500':   {'icon':'🎯','label_ar':'500 نقطة ألعاب','label_en':'500 Game Points','cat':'game'},
    'goal_1':     {'icon':'🎯','label_ar':'أول هدف','label_en':'First Goal','cat':'goals'},
    'goal_done_1':{'icon':'✅','label_ar':'أنجزت هدفاً','label_en':'Goal Complete','cat':'goals'},
    'breath_5':   {'icon':'🫁','label_ar':'5 جلسات تنفس','label_en':'5 Breathing Sessions','cat':'health'},
    'survey_1':   {'icon':'📊','label_ar':'أول استبيان','label_en':'First Survey','cat':'survey'},
    'welcome':    {'icon':'🌟','label_ar':'أهلاً بك!','label_en':'Welcome!','cat':'welcome'},
}

def get_streak(user_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM streaks WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (user_id,))
            conn.commit()
            return {'current':0,'longest':0,'total_days':0,'last_activity':None}
        return {'current':row['current_streak'],'longest':row['longest_streak'],
                'total_days':row['total_days'],'last_activity':row['last_activity']}
    finally:
        conn.close()

def update_streak(user_id):
    from datetime import date, timedelta
    today = str(date.today())
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (user_id,))
        row = conn.execute("SELECT * FROM streaks WHERE user_id=?", (user_id,)).fetchone()
        last = row['last_activity']
        current = row['current_streak']
        longest = row['longest_streak']
        total = row['total_days']
        incremented = False
        new_badge = None
        if last == today:
            pass  # Already updated today
        elif last == str(date.today() - timedelta(days=1)):
            current += 1; total += 1; incremented = True
        else:
            current = 1; total += 1; incremented = True
        if current > longest:
            longest = current
        conn.execute(
            "UPDATE streaks SET current_streak=?,longest_streak=?,total_days=?,last_activity=?,last_updated=datetime('now') WHERE user_id=?",
            (current, longest, total, today, user_id)
        )
        # Check milestone badges
        milestones = {3:'streak_3',7:'streak_7',14:'streak_14',30:'streak_30',60:'streak_60',100:'streak_100'}
        if current in milestones:
            key = milestones[current]
            conn.execute("INSERT OR IGNORE INTO achievements (user_id,badge_key) VALUES (?,?)", (user_id, key))
            badge = BADGES.get(key,{})
            if badge: new_badge = badge
        conn.commit()
        return {'current':current,'longest':longest,'total_days':total,'incremented':incremented,'new_badge':new_badge}
    finally:
        conn.close()

def get_achievements(user_id):
    conn = get_db()
    rows = conn.execute("SELECT badge_key,earned_at FROM achievements WHERE user_id=? ORDER BY earned_at DESC", (user_id,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        badge = BADGES.get(row['badge_key'],{})
        if badge:
            result.append({'key':row['badge_key'],'icon':badge['icon'],
                'label_ar':badge['label_ar'],'label_en':badge['label_en'],
                'cat':badge['cat'],'earned_at':(row['earned_at'] or '')[:10]})
    return result

def award_achievement(user_id, badge_key):
    if badge_key not in BADGES: return False
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO achievements (user_id,badge_key) VALUES (?,?)", (user_id, badge_key))
        changed = conn.total_changes
        conn.commit()
        return changed > 0
    except: return False
    finally: conn.close()

def check_and_award_achievements(user_id):
    conn = get_db()
    new_badges = []
    try:
        existing = {r['badge_key'] for r in conn.execute("SELECT badge_key FROM achievements WHERE user_id=?", (user_id,)).fetchall()}
        def award(key):
            if key not in existing and key in BADGES:
                conn.execute("INSERT OR IGNORE INTO achievements (user_id,badge_key) VALUES (?,?)", (user_id, key))
                new_badges.append(BADGES[key])
                existing.add(key)
        award('welcome')
        jc = conn.execute("SELECT COUNT(*) AS c FROM journals WHERE user_id=?", (user_id,)).fetchone()['c']
        if jc>=1: award('journal_1')
        if jc>=10: award('journal_10')
        if jc>=50: award('journal_50')
        sc = conn.execute("SELECT COUNT(*) AS c FROM surveys WHERE user_id=?", (user_id,)).fetchone()['c']
        if sc>=1: award('survey_1')
        gc = conn.execute("SELECT COUNT(*) AS c FROM goals WHERE user_id=?", (user_id,)).fetchone()['c']
        gdc = conn.execute("SELECT COUNT(*) AS c FROM goals WHERE user_id=? AND status='completed'", (user_id,)).fetchone()['c']
        if gc>=1: award('goal_1')
        if gdc>=1: award('goal_done_1')
        bc = conn.execute("SELECT COUNT(*) AS c FROM breathing_sessions WHERE user_id=?", (user_id,)).fetchone()['c']
        if bc>=5: award('breath_5')
        gt = conn.execute("SELECT COALESCE(SUM(score),0) AS s FROM game_scores WHERE user_id=?", (user_id,)).fetchone()['s']
        if gt>=100: award('game_100')
        if gt>=500: award('game_500')
        conn.commit()
    finally:
        conn.close()
    return [b for b in new_badges if b]

# ─── Save survey (10 questions) ───────────────────────────────────────────────
def save_survey(user_id, answers, notes=""):
    """Save 10-question survey with graceful fallback to 5-question."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO surveys (user_id,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, answers.get("q1"), answers.get("q2"), answers.get("q3"),
             answers.get("q4"), answers.get("q5"), answers.get("q6"),
             answers.get("q7"), answers.get("q8"), answers.get("q9"),
             answers.get("q10"), (notes or "")[:500])
        )
        conn.commit()
    except Exception:
        # Fallback for old schema (5 questions)
        conn.execute(
            "INSERT INTO surveys (user_id,q1,q2,q3,q4,q5,notes) VALUES (?,?,?,?,?,?,?)",
            (user_id, answers.get("q1"), answers.get("q2"), answers.get("q3"),
             answers.get("q4"), answers.get("q5"), (notes or "")[:500])
        )
        conn.commit()
    finally:
        conn.close()


# ─── Audit Log ────────────────────────────────────────────────────────────────
def log_counselor_action(counselor_id: int, action: str, detail: str = ""):
    """[S28] Log counselor actions for audit trail."""
    import logging
    logging.getLogger('schoolmind.audit').info(
        f"counselor_id={counselor_id} action={action} detail={detail[:200]}"
    )

# ─── Community Tips ────────────────────────────────────────────────────────────
def get_approved_tips(limit: int = 20) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT ct.*, u.anonymous_code FROM community_tips ct "
        "JOIN users u ON u.id=ct.user_id WHERE ct.is_approved=1 "
        "ORDER BY ct.likes DESC, ct.created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close(); return rows

def submit_tip(user_id: int, tip_ar: str, tip_en: str = "", category: str = "general"):
    conn = get_db()
    conn.execute(
        "INSERT INTO community_tips (user_id,tip_ar,tip_en,category,is_approved) VALUES (?,?,?,?,1)",
        (user_id, tip_ar[:300], tip_en[:300], category)
    )
    conn.commit(); conn.close()
