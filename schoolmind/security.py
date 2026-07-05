import time
import secrets
import hmac
from functools import wraps
from urllib.parse import urlencode, urlparse, urljoin
from flask import abort, request, session, g, current_app, redirect

RATE_BUCKETS = {}
RATE_LIMIT_CLEANUP_INTERVAL = 600  # Clean every 10 minutes
_LAST_CLEANUP_TIME = 0


SENSITIVE_PATH_PREFIXES = (
    "/app",
    "/student",
    "/teacher",
    "/counselor",
    "/admin",
    "/platform",
    "/api/export",
    "/account",
)
AUTH_PATH_PREFIXES = ("/login", "/forgot-password", "/reset-password", "/start")


def same_origin_url(target):
    """Return True only when a redirect target stays on this application's origin.

    request.referrer and next-like values are user-controlled enough that they must
    be treated as untrusted. Relative paths are allowed; absolute external URLs are
    rejected.
    """
    if not target:
        return False
    target_text = str(target).strip()
    if target_text.startswith(("//", "\\")):
        return False
    host_url = request.host_url
    resolved = urlparse(urljoin(host_url, target_text))
    host = urlparse(host_url)
    return resolved.scheme in {"http", "https"} and resolved.scheme == host.scheme and resolved.netloc == host.netloc


def safe_redirect(target, fallback_endpoint="public.index", **fallback_values):
    """Redirect to a same-origin target or a safe Flask endpoint fallback."""
    if same_origin_url(target):
        return redirect(target)
    from flask import url_for

    return redirect(url_for(fallback_endpoint, **fallback_values))


def safe_referrer_redirect(fallback_endpoint="public.index", **fallback_values):
    """Redirect back only when the referrer is same-origin."""
    return safe_redirect(request.referrer, fallback_endpoint, **fallback_values)


def current_csp_nonce():
    nonce = getattr(g, "csp_nonce", None)
    if not nonce:
        nonce = secrets.token_urlsafe(18)
        g.csp_nonce = nonce
    return nonce


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("csrf_token")
    if not sent or not expected or not hmac.compare_digest(str(sent), str(expected)):
        abort(400, "Invalid CSRF token")


def require_csrf(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            validate_csrf()
        return view(*args, **kwargs)
    return wrapper


def _cleanup_expired_buckets(window_seconds):
    """Remove stale entries from rate limit buckets to prevent memory growth."""
    global _LAST_CLEANUP_TIME
    now = time.time()
    if now - _LAST_CLEANUP_TIME < RATE_LIMIT_CLEANUP_INTERVAL:
        return
    
    _LAST_CLEANUP_TIME = now
    to_delete = []
    for key, bucket in RATE_BUCKETS.items():
        # Filter out expired entries
        filtered = [stamp for stamp in bucket if now - stamp < window_seconds]
        if filtered:
            RATE_BUCKETS[key] = filtered
        else:
            # Mark key for deletion if bucket is empty
            to_delete.append(key)
    
    # Delete empty buckets
    for key in to_delete:
        del RATE_BUCKETS[key]


def client_ip():
    """Return a client IP without blindly trusting spoofable proxy headers.

    Production deployments behind a trusted proxy can set TRUST_PROXY_HEADERS=true.
    Without that flag, the app uses request.remote_addr so direct clients cannot
    spoof rate-limit and audit IPs with X-Forwarded-For.
    """
    remote = request.remote_addr or "unknown"
    try:
        trust_proxy = bool(current_app.config.get("TRUST_PROXY_HEADERS", False))
    except RuntimeError:
        trust_proxy = False
    if not trust_proxy:
        return remote.strip() or "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        candidate = forwarded_for.split(",")[0].strip()
        if candidate:
            return candidate
    return remote.strip() or "unknown"


def rate_limit(scope, max_requests=40, window_seconds=300):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            now = time.time()
            ip = client_ip()
            key = f"{scope}:{ip}"
            
            # Periodic cleanup to prevent memory leaks
            _cleanup_expired_buckets(window_seconds)
            
            bucket = [stamp for stamp in RATE_BUCKETS.get(key, []) if now - stamp < window_seconds]
            if len(bucket) >= max_requests:
                abort(429)
            bucket.append(now)
            RATE_BUCKETS[key] = bucket
            return view(*args, **kwargs)
        return wrapper
    return decorator


def localized_current_url(language):
    args = request.args.to_dict(flat=True)
    args["language"] = language
    return request.path + "?" + urlencode(args)


def inject_security_context():
    settings = {}
    try:
        from .db import query_all

        settings = {row["key"]: row["value"] for row in query_all("SELECT key, value FROM site_settings")}
    except Exception:
        settings = {}
    try:
        from .i18n import FONT_SIZES, SUPPORTED_LANGUAGES, SUPPORTED_THEMES, normalize_language, normalize_theme, translate

        prefs = getattr(g, "preferences", None) or getattr(g, "platform_preferences", None)
        session_language = session.get("language", "en")
        session_theme = session.get("theme", "dark")
        language = normalize_language(prefs["language"] if prefs else session_language)
        theme = normalize_theme(prefs["theme"] if prefs else session_theme)
        high_contrast = bool(prefs["high_contrast"]) if prefs and "high_contrast" in prefs.keys() else bool(session.get("high_contrast", theme == "high-contrast"))
        reduced_motion = bool(prefs["reduced_motion"]) if prefs and "reduced_motion" in prefs.keys() else bool(session.get("reduced_motion", False))
        dyslexia = bool(prefs["dyslexia_friendly"]) if prefs and "dyslexia_friendly" in prefs.keys() else bool(session.get("dyslexia_friendly", False))
        session_font_size = session.get("font_size", "normal")
        font_size = prefs["font_size"] if prefs and prefs["font_size"] in FONT_SIZES else session_font_size if session_font_size in FONT_SIZES else "normal"
        language_meta = SUPPORTED_LANGUAGES[language]
        if prefs:
            completed = bool(prefs["personalization_completed"]) if "personalization_completed" in prefs.keys() else False
            dismissed = bool(prefs["personalization_dismissed"]) if "personalization_dismissed" in prefs.keys() else False
        else:
            completed = bool(session.get("personalization_completed", False))
            dismissed = bool(session.get("personalization_dismissed", False))
        show_personalization = not completed and not dismissed
    except Exception:
        FONT_SIZES = {"normal": "Normal"}
        SUPPORTED_LANGUAGES = {"en": {"name": "English", "dir": "ltr"}}
        SUPPORTED_THEMES = {"dark": "Dark"}
        translate = lambda key, language="en": key
        language = "en"
        theme = "dark"
        language_meta = SUPPORTED_LANGUAGES["en"]
        high_contrast = False
        reduced_motion = False
        dyslexia = False
        font_size = "normal"
        show_personalization = False
    return {
        "csrf_token": csrf_token,
        "current_user": getattr(g, "user", None),
        "current_platform_admin": getattr(g, "platform_admin", None),
        "site_settings": settings,
        "current_language": language,
        "current_dir": language_meta["dir"],
        "current_theme": "high-contrast" if high_contrast else theme,
        "current_font_size": font_size,
        "current_high_contrast": high_contrast,
        "current_reduced_motion": reduced_motion,
        "current_dyslexia": dyslexia,
        "show_personalization": show_personalization,
        "supported_languages": SUPPORTED_LANGUAGES,
        "supported_themes": SUPPORTED_THEMES,
        "font_sizes": FONT_SIZES,
        "t": lambda key: translate(key, language),
        "language_url": localized_current_url,
        "csp_nonce": current_csp_nonce,
    }


def build_content_security_policy():
    directives = [
        "default-src 'self'",
        "img-src 'self' data: https:",
        f"script-src 'self' 'nonce-{current_csp_nonce()}'",
        "style-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ]
    report_uri = str(current_app.config.get("CSP_REPORT_URI", "") or "").strip()
    if report_uri:
        directives.append(f"report-uri {report_uri}")
    if current_app_env() == "production":
        directives.append("upgrade-insecure-requests")
    return "; ".join(directives)


def path_needs_no_store():
    path = request.path or ""
    if path.startswith(SENSITIVE_PATH_PREFIXES) or path.startswith(AUTH_PATH_PREFIXES):
        return True
    if getattr(g, "user", None) is not None or getattr(g, "platform_admin", None) is not None:
        return True
    return False


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("X-DNS-Prefetch-Control", "off")
    response.headers.setdefault("Origin-Agent-Cluster", "?1")
    csp = build_content_security_policy()
    if current_app.config.get("CSP_REPORT_ONLY", False):
        response.headers.setdefault("Content-Security-Policy-Report-Only", csp)
    else:
        response.headers.setdefault("Content-Security-Policy", csp)
    if current_app_env() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    if path_needs_no_store():
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def current_app_env():
    try:
        from flask import current_app

        return current_app.config.get("APP_ENV", "development")
    except RuntimeError:
        return "development"
