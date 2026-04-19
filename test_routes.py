"""
Smoke-test every route using Flask's test_client.
Tests both unauthenticated and authenticated flows.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

def check(status, allowed, desc):
    ok = status in (allowed if isinstance(allowed, (list, tuple, set)) else [allowed])
    badge = PASS if ok else FAIL
    print(f"  {badge} [{status}] {desc}")
    return ok

total = 0
passed = 0

print("\n━━━ UNAUTHENTICATED ROUTES ━━━")
with app.test_client() as c:
    for path, allowed in [
        ("/",                 [302]),
        ("/ping",              200),
        ("/health",            200),
        ("/robots.txt",        200),
        ("/sitemap.xml",       200),
        ("/login",             200),
        ("/register",          200),
        ("/register/anonymous", 200),
        ("/forgot-password",   200),
        ("/student",          [302]),         # Redirect to login
        ("/counselor",        [302]),         # Redirect to login
        ("/api/streak",       [302, 401]),    # Login required
        ("/unknown-route",    [404, 302]),    # 404 or safe redirect
    ]:
        r = c.get(path, follow_redirects=False)
        total += 1
        if check(r.status_code, allowed, path):
            passed += 1

print("\n━━━ STUDENT LOGIN ━━━")
with app.test_client() as c:
    # Get CSRF token from login page
    r = c.get("/login")
    assert r.status_code == 200
    # Parse csrf
    html = r.data.decode("utf-8", "ignore")
    # Login form uses form field csrf_token — we need it from session
    with c.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    assert csrf, "No CSRF token in session"
    r = c.post("/login", data={
        "username": "student1",
        "password": "pass123",
        "csrf_token": csrf,
    }, follow_redirects=False)
    total += 1
    if check(r.status_code, [302], "POST /login student1 (expect redirect)"):
        passed += 1
    with c.session_transaction() as sess:
        uid = sess.get("user_id")
        role = sess.get("role")
    total += 1
    if check(uid is not None and role == "student", [True], f"Session created uid={uid} role={role}"):
        passed += 1

print("\n━━━ STUDENT AUTHENTICATED ROUTES ━━━")
with app.test_client() as c:
    # Login first
    c.get("/login")
    with c.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    c.post("/login", data={"username":"student1","password":"pass123","csrf_token":csrf})

    for path, allowed in [
        ("/student",               200),
        ("/student/stats",         200),
        ("/student/profile",       200),
        ("/journal",               200),
        ("/survey",                200),
        ("/companion",             200),
        ("/emergency",             200),
        ("/resources",             200),
        ("/games",                 200),
        ("/goals",                 200),
        ("/breathing-center",      200),
        ("/achievements",          200),
        ("/about",                 200),
        ("/accessibility",         200),
        ("/mood-diary",            200),
        ("/daily-tips",            200),
        ("/relaxation",            200),
        ("/school-map",           [200, 302]),
        ("/export-report",         200),
        ("/api/streak",            200),
        ("/api/quick-stats",       200),
        ("/api/daily-status",      200),
        ("/api/mood-trend",        200),
        ("/counselor",            [302]),     # Student can't access counselor
    ]:
        r = c.get(path, follow_redirects=False)
        total += 1
        if check(r.status_code, allowed, path):
            passed += 1

print("\n━━━ COUNSELOR LOGIN ━━━")
with app.test_client() as c:
    c.get("/login")
    with c.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    r = c.post("/login", data={
        "username":"counselor1","password":"counsel123","csrf_token":csrf
    }, follow_redirects=False)
    total += 1
    if check(r.status_code, [302], "POST /login counselor1"):
        passed += 1
    with c.session_transaction() as sess:
        assert sess.get("role") == "counselor"

print("\n━━━ COUNSELOR AUTHENTICATED ROUTES ━━━")
with app.test_client() as c:
    c.get("/login")
    with c.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    c.post("/login", data={"username":"counselor1","password":"counsel123","csrf_token":csrf})

    for path, allowed in [
        ("/counselor",             200),
        ("/counselor/profile",     200),
        ("/counselor/students",    200),
        ("/counselor/export-csv",  200),
        ("/counselor/locations",   200),
        ("/research",              200),
        ("/school-map",            200),
        ("/api/search-students",   200),
        ("/api/statistics",        200),
        ("/student",              [200, 302]),
    ]:
        r = c.get(path, follow_redirects=False)
        total += 1
        if check(r.status_code, allowed, path):
            passed += 1

print("\n━━━ CSRF PROTECTION ━━━")
with app.test_client() as c:
    # POST without CSRF should be rejected
    r = c.post("/login", data={"username":"student1","password":"pass123"},
               follow_redirects=False)
    total += 1
    # Without CSRF, it should redirect back to login with flash (302)
    if check(r.status_code, [302], "POST without CSRF → redirect"):
        passed += 1

print("\n━━━ SECURITY HEADERS ━━━")
with app.test_client() as c:
    r = c.get("/login")
    headers = dict(r.headers)
    total += 1
    if check("X-Content-Type-Options" in headers, [True], "X-Content-Type-Options set"):
        passed += 1
    total += 1
    if check("Content-Security-Policy" in headers, [True], "CSP set"):
        passed += 1
    total += 1
    if check("'unsafe-inline'" not in headers.get("Content-Security-Policy",""), [True],
             "CSP script-src does NOT contain 'unsafe-inline'"):
        # Check specifically for script-src (style-src is still unsafe-inline which is ok)
        csp = headers.get("Content-Security-Policy","")
        # Parse script-src section
        for directive in csp.split(";"):
            directive = directive.strip()
            if directive.startswith("script-src"):
                if "unsafe-inline" not in directive:
                    passed += 1
                    break
        else:
            passed += 1  # no script-src found, default applies  

print("\n" + "━" * 60)
print(f"  RESULT: {passed}/{total} tests passed")
print("━" * 60)

sys.exit(0 if passed == total else 1)
