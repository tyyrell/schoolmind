# SchoolMind AI v21

Mental-health platform for school students (Arabic + English).
Built with Flask, SQLite, and a rule-based Arabic/English emotion analyzer ("Nour").

**Project:** T354 · **Competition:** JoYS 2026

---

## What's new in v21

v21 is a security + structure refactor of v20, plus a Groq AI integration.
Everything that worked before still works; the big changes are under the hood.

**AI integration**
- `ai_model/groq_service.py` — clean wrapper around Groq's chat completions API
- Reads `GROQ_API_KEY` from environment only; never logged, never in frontend
- 20-second timeout, 1 retry on 5xx/timeout, silent fallback to local rule-based "Nour" on any failure
- Natural friend-style prompts (not clinical), matches user's dialect, 3-6 sentence replies
- Safety is enforced server-side: crisis-keyword pre-filter in `app.py` always appends emergency contact info to replies containing self-harm keywords (Arabic + English), regardless of whether Groq or local engine generated the text
- `max_tokens=320`, history truncated to 8 turns, input capped at 1000 chars
- 18 unit tests in `test_groq.py` (mocked, no network required)

**Design system**
- Single `static/css/app.css` (~50 KB) — clean Stripe/Notion-level palette
- Light mode: `#f8fafc` bg, `#0ea5e9` primary, `#22c55e` accent
- Dark mode: `#0f172a` bg, `#1e293b` surface, `#38bdf8` primary
- 8px spacing scale, 0.15–0.3s transitions, subtle neutral shadows
- No glassmorphism, no gradient spam, no heavy animations

**Security**
- Centralized security helpers in `security.py` (CSRF, input cleaning, constant-time compares, safe redirects, CSV-injection defense)
- `ProxyFix` middleware when behind a reverse proxy (Render)
- Stricter security headers: `COOP`, `CORP`, tightened `Permissions-Policy`, and a tightened CSP (object-src/frame-src/base-uri/form-action all locked)
- Password reset no longer flashes the temp password — it's shown once on a dedicated page
- CSRF token is rotated on login/register/logout (session-fixation defense)
- Avatar upload does magic-byte + WEBP-marker verification (not just extension trust)
- Counselor authorization is now enforced on `student_detail` and `edit_student` (previously a counselor could access any student)
- Game scores validated against an allow-list and hard-capped
- Secret key length is validated on boot

**Structure**
- New design-system CSS split into 3 cacheable files (`design-system.css`, `components.css`, `layout.css`)
- `base.html` rewritten; inline `<style>` block removed in favor of external CSS
- Auth pages (login, register, anon register, forgot-password, 404) completely redesigned with a consistent "auth-card" pattern
- `student_dashboard`, `journal`, and `counselor_dashboard` redesigned
- Proper light + dark modes with design tokens
- Automated route test suite in `test_routes.py` (53 tests passing)

**What hasn't changed**
- `database.py` schema and queries (no DB migration needed)
- `ai_model/analyzer.py` (Nour is untouched)
- Templates other than the ones listed above still work via backward-compatible CSS classes

---

## Repo layout

```
schoolmind/
├── app.py                     # Flask routes (single file)
├── database.py                # SQLite schema + queries
├── security.py                # CSRF, input cleaning, auth decorators
├── ai_model/
│   └── analyzer.py            # Nour — rule-based emotion engine
├── setup_demo.py              # Creates DB + demo users
├── test_routes.py             # Automated smoke tests
├── requirements.txt
├── Procfile
├── render.yaml                # Render deployment config
├── static/
│   ├── css/
│   │   ├── design-system.css  # Tokens: colors, type, spacing, motion
│   │   ├── components.css     # Buttons, cards, forms, alerts
│   │   └── layout.css         # Sidebar, topbar, bottom nav
│   ├── js/
│   │   └── app.js             # Core JS — no dependencies
│   └── images/                # (your logos go here: logo1.png, logo2.png)
├── templates/                 # 28 Jinja2 templates
└── database/                  # SQLite DB (gitignored in production)
```

---

## Running locally

```bash
pip install -r requirements.txt
python setup_demo.py        # creates DB + demo users
python app.py               # runs at http://127.0.0.1:5000
```

Demo accounts:
- Students: `student1` / `pass123`, `student2`, `student3`, `student4`
- Counselor: `counselor1` / `counsel123`

## Running tests

```bash
python test_routes.py
```

Should print `53/54 tests passed` (the one "fail" is a note that CSP allows `unsafe-inline` in `script-src` — this is intentional for template compatibility; see **Security notes** below).

---

## Deployment (Render)

`render.yaml` is pre-configured. You need to:

1. **Set `SECRET_KEY`** — at least 32 bytes. `render.yaml` sets `generateValue: true` so Render will generate one for you.
2. **Attach a persistent disk** at `/data` (already in `render.yaml`) — SQLite DB goes there so it survives deploys.
3. Push to your connected git repo → Render auto-deploys.

Environment variables:
| Var | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing key — must be 32+ chars |
| `RENDER=1` | Enables HTTPS-only cookies and HSTS |
| `DB_PATH` | Path to SQLite file (defaults to `/data/schoolmind.db` on Render) |
| `FLASK_DEBUG` | `1` only for local dev. Never set in production. |
| `FORCE_HTTPS` | Set to `1` on non-Render HTTPS hosts |
| `GROQ_API_KEY` | Optional. If set, Nour uses Groq AI; otherwise falls back to local engine. |
| `GROQ_MODEL` | Optional. Defaults to `llama-3.1-8b-instant`. |

---

## Security notes (honest version)

**What's genuinely strong:**
- Passwords hashed with `werkzeug.security.generate_password_hash` (PBKDF2-SHA256)
- All parameterized SQL queries (no string concatenation into SQL)
- Jinja2 autoescape is on for all template variables
- CSRF tokens on every POST, verified constant-time
- Rate limiting on every mutating endpoint
- Session cookies: HttpOnly, Secure (in prod), SameSite=Lax
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, full HSTS when HTTPS
- Strict Permissions-Policy and tight CSP for most directives

**Known compromises (with reasons):**
- `script-src` still allows `'unsafe-inline'`. Why: 25 of the 28 templates use inline `onclick` handlers. Moving them all into `addEventListener` is a mechanical refactor that would take several more hours and adds risk of breaking features. Jinja2 autoescape + server-side `clean_text()` still stop reflected XSS, but if you later rewrite those handlers, remove `'unsafe-inline'` from the CSP string in `app.py` (one-line change).
- `style-src` also allows `'unsafe-inline'` — this is needed for dynamic styles via `style="..."` attributes in some pages. The risk here is minimal (CSS injection ≠ script execution).
- Rate limiter is in-memory. It resets on restart and doesn't coordinate across gunicorn workers. For a school pilot this is fine; for a scaled deployment, swap for Redis.
- Session fingerprint uses User-Agent + Accept-Language. This catches naive session cookie theft but not a determined attacker on the same network.

**Not claimed:**
- No penetration test done
- No third-party dependency audit run
- Not a replacement for real student mental-health services — provide crisis-line info prominently (see `templates/emergency.html`)

---

## Development tips

- To tighten CSP further: remove `'unsafe-inline'` from `script-src` in `app.py` and move the remaining `onclick="…"` attributes into `static/js/app.js` as `addEventListener` calls.
- To add a new page: create `templates/my_page.html` extending `base.html`, then add a route in `app.py`.
- To change theme colors: edit the `:root` block in `static/css/design-system.css`. Dark mode overrides are in `[data-theme="dark"]` below.
- DB migrations: new columns are added idempotently in `init_db()` — see the `q11..q20` example.

---

## License

Educational project — JoYS 2026 competition submission.
