"""
SchoolMind AI v16 — Demo Setup Script
يُنشئ حسابات تجريبية عند أول تشغيل
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, register_user, get_db

def setup():
    print("⚙️  SchoolMind AI v16 — Setup...")
    init_db()
    print("✅  Database initialized")

    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    conn.close()

    if existing > 0:
        print(f"ℹ️  {existing} users already exist — skipping demo creation")
        print("✅  Setup complete!")
        return

    demos = [
        ("student1", "pass123", "student", "أحمد الخالدي", "الصف العاشر"),
        ("student2", "pass123", "student", "سارة النجار", "الصف التاسع"),
        ("student3", "pass123", "student", "خالد الرشيد", "الصف الحادي عشر"),
        ("student4", "pass123", "student", "ريم العبدالله", "الصف الثامن"),
        ("counselor1", "counsel123", "counselor", "المرشد محمد العمري", None),
    ]

    for username, password, role, name, grade in demos:
        sup = ["الصف السابع","الصف الثامن","الصف التاسع","الصف العاشر","الصف الحادي عشر","الصف الثاني عشر"] if role=="counselor" else None
        ok, result = register_user(username, password, role, name, grade, sup)
        if ok:
            print(f"   ✅  {role}: {username} / {password}")
        else:
            print(f"   ⚠️  {username}: {result}")

    print("\n" + "="*50)
    print("  SchoolMind AI v16 — حسابات تجريبية")
    print("="*50)
    print("  👤 student1   / pass123")
    print("  👤 student2   / pass123")
    print("  👤 student3   / pass123")
    print("  👤 student4   / pass123")
    print("  🎓 counselor1 / counsel123")
    print("="*50 + "\n")
    print("✅  Setup complete!")

if __name__ == "__main__":
    setup()
