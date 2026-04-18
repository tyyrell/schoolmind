"""
SchoolMind AI v21 — Security utilities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shared helpers for input sanitization, validation, CSRF, headers, etc.

Centralizing these in one module makes auditing easier and prevents
inconsistent application of security policies across routes.
"""
import re
import secrets
import hashlib
import html as _html
import logging
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, flash, abort

log = logging.getLogger("schoolmind.security")

# ──────────────────────────────────────────────────────────────────────────
# Input cleaning & validation
# ──────────────────────────────────────────────────────────────────────────

# Allowed character sets
_USERNAME_RE = re.compile(r"[^a-zA-Z0-9_\u0600-\u06FF\-]")
_DIGITS_RE   = re.compile(r"[^0-9]")
_DATE_RE     = re.compile(r"[^0-9\-]")
# Strip *all* HTML tags (not just simple ones). Defends against tag obfuscation.
_TAG_RE      = re.compile(r"<[^>]*>")
# Control characters except common whitespace (\n, \t)
_CTRL_RE     = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(s, maxlen=5000):
    """
    Clean user-supplied text.
    - Removes HTML tags (defense in depth — Jinja autoescapes anyway)
    - Removes control chars
    - Normalizes whitespace
    - Trims to max length
    """
    if s is None:
        return ""
    s = str(s)
    s = _CTRL_RE.sub("", s)
    s = _TAG_RE.sub("", s)
    s = s.strip()
    return s[:maxlen]


def clean_username(s, maxlen=40):
    """Username: alnum + underscore + hyphen + Arabic letters only."""
    if s is None:
        return ""
    s = str(s).strip()
    s = _USERNAME_RE.sub("", s)
    return s[:maxlen]


def clean_digits(s, maxlen=20):
    """Strip all non-digit characters."""
    if s is None:
        return ""
    return _DIGITS_RE.sub("", str(s))[:maxlen]


def clean_date(s, maxlen=10):
    """Date: digits and hyphen only."""
    if s is None:
        return ""
    return _DATE_RE.sub("", str(s))[:maxlen]


def csv_safe_cell(value):
    """
    Defend against CSV formula injection (CWE-1236).
    If a cell starts with one of these characters, prefix it with a single quote.
    See OWASP "CSV Injection".
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


# ──────────────────────────────────────────────────────────────────────────
# Constant-time string comparison
# ──────────────────────────────────────────────────────────────────────────

def safe_compare(a, b):
    """Constant-time string comparison to prevent timing attacks."""
    if a is None or b is None:
        return False
    return secrets.compare_digest(str(a), str(b))


# ──────────────────────────────────────────────────────────────────────────
# CSRF protection
# ──────────────────────────────────────────────────────────────────────────

CSRF_HEADER = "X-CSRF-Token"
CSRF_FIELD  = "csrf_token"


def issue_csrf_token():
    """Generate or fetch the per-session CSRF token."""
    if CSRF_FIELD not in session:
        session[CSRF_FIELD] = secrets.token_urlsafe(32)
    return session[CSRF_FIELD]


def rotate_csrf_token():
    """Generate a new CSRF token (use after login/logout)."""
    session[CSRF_FIELD] = secrets.token_urlsafe(32)
    return session[CSRF_FIELD]


def verify_csrf():
    """
    Returns None if valid, or a Flask response (redirect/json) if invalid.
    Use as: `chk = verify_csrf();  if chk: return chk`
    """
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return None
    token = request.form.get(CSRF_FIELD) or request.headers.get(CSRF_HEADER, "")
    expected = session.get(CSRF_FIELD)
    if not expected or not token or not safe_compare(token, expected):
        log.warning(
            "CSRF mismatch path=%s ip=%s ua=%s",
            request.path,
            client_ip(),
            request.headers.get("User-Agent", "")[:50],
        )
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "csrf_invalid"}), 403
        flash("انتهت صلاحية الجلسة. يرجى المحاولة مجدداً" , "error")
        return redirect(safe_referrer())
    return None


# ──────────────────────────────────────────────────────────────────────────
# Safe redirect
# ──────────────────────────────────────────────────────────────────────────

def safe_referrer(default_endpoint="index"):
    """Return request.referrer if it's same-origin, else a safe default."""
    ref = request.referrer or ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(ref)
        host = urlparse(request.url).netloc
        # Same origin or relative URL only
        if parsed.netloc in ("", host) and not ref.startswith(("javascript:", "data:", "vbscript:")):
            return ref
    except Exception:
        pass
    try:
        return url_for(default_endpoint)
    except Exception:
        return "/"


# ──────────────────────────────────────────────────────────────────────────
# Session fingerprinting
# ──────────────────────────────────────────────────────────────────────────

def session_fingerprint():
    """
    Compute a stable but private fingerprint from the request.
    Combined with a server-side secret would be ideal; for now we use
    User-Agent + Accept-Language to detect simple session hijacking.
    """
    parts = [
        request.headers.get("User-Agent", "")[:120],
        request.headers.get("Accept-Language", "")[:40],
    ]
    return hashlib.sha256(("|".join(parts)).encode("utf-8")).hexdigest()[:24]


# ──────────────────────────────────────────────────────────────────────────
# Client IP (respects proxies cautiously)
# ──────────────────────────────────────────────────────────────────────────

def client_ip():
    """
    Return the client IP, taking the FIRST entry of X-Forwarded-For if set.
    Note: trust this only when behind a reverse proxy (Render does set this).
    """
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.remote_addr or "unknown"


# ──────────────────────────────────────────────────────────────────────────
# JSON validation helper
# ──────────────────────────────────────────────────────────────────────────

MAX_JSON_BYTES = 64 * 1024  # 64 KB


def get_json_or_error():
    """
    Parse incoming JSON safely. Returns (data, None) on success,
    or (None, error_response_tuple) on failure.
    """
    if request.content_length and request.content_length > MAX_JSON_BYTES:
        return None, (jsonify({"error": True, "message": "payload too large"}), 413)
    if not request.is_json:
        return None, (jsonify({"error": True, "message": "JSON required"}), 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": True, "message": "invalid JSON"}), 400)
    return data, None


# ──────────────────────────────────────────────────────────────────────────
# JSON responses
# ──────────────────────────────────────────────────────────────────────────

def api_error(message, status=400, **extra):
    body = {"error": True, "message": str(message)[:300], "code": status}
    body.update(extra)
    return jsonify(body), status


def api_ok(data=None, **extra):
    body = {"ok": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return jsonify(body)


# ──────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────

def login_required(get_user_by_id):
    """
    Factory: returns the decorator. We accept get_user_by_id as a parameter
    to avoid a circular import with the database module.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("يرجى تسجيل الدخول", "error")
                return redirect(url_for("login"))
            try:
                fp = session.get("_fp")
                if fp and not safe_compare(fp, session_fingerprint()):
                    log.warning("Fingerprint mismatch uid=%s", session.get("user_id"))
                    session.clear()
                    flash("انتهت الجلسة لأسباب أمنية", "error")
                    return redirect(url_for("login"))
                user = get_user_by_id(session["user_id"])
                if not user or not user["is_active"]:
                    session.clear()
                    flash("يرجى تسجيل الدخول", "error")
                    return redirect(url_for("login"))
            except Exception as e:
                log.error("login_required error: %s", e)
                session.clear()
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def role_required(role, get_user_by_id):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session or session.get("role") != role:
                flash("غير مصرح", "error")
                return redirect(url_for("login"))
            try:
                user = get_user_by_id(session["user_id"])
                if not user or not user["is_active"]:
                    session.clear()
                    flash("غير مصرح", "error")
                    return redirect(url_for("login"))
            except Exception as e:
                log.error("role_required error: %s", e)
                session.clear()
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator
