"""
SchoolMind AI v13 — Demo Setup Script
Creates demo accounts and sample data for testing.
Run: python setup_demo.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, register_user, get_db, save_journal, save_checkin
from ai_model.analyzer import analyze_text, calculate_risk_score

def setup():
    print("🧠 SchoolMind AI v13 — Setting up demo data...")

    # Initialize database
    init_db()
    print("✅ Database initialized")

    # Create demo accounts
    accounts = [
        # (username, password, role, name, grade/sup, national_id, birthdate)
        ("student1", "pass123", "student", "طالب تجريبي أول",  "الصف العاشر", "1234567890", "2008-05-15"),
        ("student2", "pass123", "student", "طالبة تجريبية",    "الصف الحادي عشر", "0987654321", "2007-09-20"),
        ("student3", "pass123", "student", "طالب ثالث",        "الصف التاسع",  None, None),
        ("counselor1", "counsel123", "counselor", "المرشد أحمد", None, "1111111111", "1985-03-10"),
    ]

    created = {}
    conn = get_db()

    for uname, pw, role, name, grade_or_sup, nid, bday in accounts:
        # Check if exists
        existing = conn.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone()
        if existing:
            print(f"  ℹ️  {uname} already exists — skipping")
            created[uname] = existing["id"]
            continue

        if role == "counselor":
            sup = ["الصف العاشر", "الصف الحادي عشر", "الصف التاسع",
                   "الصف الثامن", "الصف السابع", "الصف الثاني عشر"]
            ok, uid = register_user(uname, pw, role, name, supervised_grades=sup,
                                    national_id=nid, birthdate=bday)
        else:
            ok, uid = register_user(uname, pw, role, name, grade=grade_or_sup,
                                    national_id=nid, birthdate=bday)
        if ok:
            print(f"  ✅ Created {role}: {uname} / {pw}")
            created[uname] = uid
        else:
            print(f"  ❌ Failed to create {uname}: {uid}")

    conn.close()

    # Add sample journals for student1
    if "student1" in created:
        uid = created["student1"]
        conn = get_db()
        existing_journals = conn.execute(
            "SELECT COUNT(*) AS c FROM journals WHERE user_id=?", (uid,)
        ).fetchone()["c"]
        conn.close()

        if existing_journals == 0:
            sample_journals = [
                ("اليوم كان يوماً صعباً في المدرسة. شعرت بالتعب والإرهاق من كثرة الواجبات.", 2),
                ("الحمد لله، اليوم كان أفضل. أصدقائي كانوا معي وساعدوني على الدراسة.", 4),
                ("أشعر بقلق كبير من الامتحانات القادمة. لا أعرف إذا سأنجح.", 2),
                ("يوم رائع! حصلت على علامة ممتازة في الرياضيات. أنا سعيد جداً.", 5),
            ]
            for content, mood in sample_journals:
                try:
                    analysis = analyze_text(content)
                    past = []
                    risk = calculate_risk_score(analysis, past)
                    save_journal(uid, content, mood, "ar", analysis, risk)
                except Exception as e:
                    # Simple fallback
                    analysis = {"dominant_emotion": "neutral", "confidence": 0.5,
                                "has_bullying": False, "negative_hits": 0,
                                "weighted_hits": 0, "neg_density": 0,
                                "category_scores": {}, "all_categories": [],
                                "is_critical": False, "found_keywords": {}, "lang": "ar"}
                    risk = {"score": 2.0, "level": "low", "color": "#10b981",
                            "max_score": 10, "factors": {}, "should_alert": False}
                    save_journal(uid, content, mood, "ar", analysis, risk)

            print(f"  ✅ Added {len(sample_journals)} sample journals for student1")

            # Add check-in
            save_checkin(uid, 3, 1, 0, "أشعر بحال معقول")
            print("  ✅ Added sample check-in for student1")

    print("\n" + "="*50)
    print("🎉 Setup complete!")
    print("="*50)
    print("\n📋 Demo Accounts:")
    print("  Student:   student1 / pass123")
    print("  Student:   student2 / pass123")
    print("  Counselor: counselor1 / counsel123")
    print("\n🚀 Run: python app.py")
    print("   URL: http://127.0.0.1:5000\n")

if __name__ == "__main__":
    setup()
