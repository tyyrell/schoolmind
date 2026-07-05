import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

ROOT = Path(__file__).resolve().parents[1]
errors = []
warnings = []


def env_bool(*names, default=False):
    for name in names:
        if name in os.environ:
            return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
    return bool(default)


def normalize_engine(value):
    normalized = (value or "").strip().lower()
    if normalized in {"postgresql", "pg"}:
        return "postgres"
    if normalized in {"sqlite3", ""}:
        return "sqlite"
    return normalized


app_env = os.environ.get("APP_ENV", "development").lower()
database_url = os.environ.get("DATABASE_URL", "").strip()
database_engine = normalize_engine(os.environ.get("DATABASE_ENGINE") or ("postgres" if database_url.lower().startswith(("postgres://", "postgresql://")) else "sqlite"))
database_sslmode = os.environ.get("DATABASE_SSLMODE", "require" if database_engine == "postgres" and app_env == "production" else "").strip().lower()
database_pooling_mode = os.environ.get("DATABASE_POOLING_MODE", "external").strip().lower()

secret = os.environ.get("SECRET_KEY", "")
if app_env == "production" and (not secret or secret == "dev-only-change-me" or len(secret) < 32):
    errors.append("SECRET_KEY must be a real 32+ character secret in production.")
elif app_env != "production" and (not secret or secret == "dev-only-change-me"):
    warnings.append("SECRET_KEY is using a development value. Set a strong secret before production.")

if database_engine not in {"sqlite", "postgres"}:
    errors.append("DATABASE_ENGINE must be sqlite or postgres.")

if database_url.lower().startswith(("postgres://", "postgresql://")) and database_engine != "postgres":
    errors.append("DATABASE_URL is PostgreSQL but DATABASE_ENGINE is not postgres. This would silently write to the wrong database.")

if database_engine == "postgres":
    if not database_url:
        errors.append("DATABASE_ENGINE=postgres requires DATABASE_URL.")
    elif not database_url.lower().startswith(("postgres://", "postgresql://")):
        errors.append("DATABASE_URL must start with postgres:// or postgresql:// for PostgreSQL.")
    else:
        parsed_db = urlparse(database_url)
        if not parsed_db.hostname:
            errors.append("DATABASE_URL must include a hostname.")
        elif "supabase" not in parsed_db.hostname and app_env == "production":
            warnings.append("DATABASE_URL does not look like a Supabase hostname. This is allowed, but verify it points to the intended managed PostgreSQL database.")
        params = {k.lower(): v for k, v in parse_qsl(parsed_db.query, keep_blank_values=True)}
        effective_sslmode = params.get("sslmode") or database_sslmode
        if parsed_db.scheme == "postgres":
            warnings.append("postgres:// is accepted and normalized to postgresql:// by the runtime.")
        if app_env == "production" and effective_sslmode not in {"require", "verify-ca", "verify-full"}:
            errors.append("Production PostgreSQL requires sslmode=require or stronger. Set DATABASE_SSLMODE=require or add ?sslmode=require to DATABASE_URL.")
        if database_pooling_mode not in {"external", "direct", "transaction", "session"}:
            errors.append("DATABASE_POOLING_MODE must be external, direct, transaction, or session.")
        if app_env == "production" and parsed_db.port not in {5432, 6543, None}:
            warnings.append("DATABASE_URL uses a non-standard PostgreSQL port. Verify Supabase pooler/direct endpoint settings.")
        if app_env == "production" and "supabase" in (parsed_db.hostname or "").lower() and parsed_db.port != 6543:
            warnings.append("Supabase production should usually use the pooler endpoint on port 6543 for web apps unless you have a direct-connection plan.")
else:
    if app_env == "production" and not (env_bool("ALLOW_SQLITE_IN_PRODUCTION") or app_env == "demo"):
        errors.append("Production requires DATABASE_ENGINE=postgres unless ALLOW_SQLITE_IN_PRODUCTION=true is set for a controlled demo exception.")
    if not os.environ.get("DATABASE_PATH") and not database_url.startswith("sqlite://"):
        warnings.append("DATABASE_PATH is not set. SQLite local/dev will use the instance folder default.")
    if database_url.startswith("sqlite:///"):
        sqlite_path = database_url.replace("sqlite:///", "", 1)
        if app_env == "production" and not sqlite_path.startswith(("/var/data/", "/data/")):
            warnings.append("SQLite DATABASE_URL should point to a persistent disk path in production demo mode.")

if app_env == "production":
    if os.environ.get("SESSION_COOKIE_SECURE", "true").lower() != "true":
        errors.append("SESSION_COOKIE_SECURE must be true in production.")
    session_cookie_name = os.environ.get("SESSION_COOKIE_NAME", "__Host-schoolmind_session")
    if not session_cookie_name.startswith("__Host-"):
        errors.append("SESSION_COOKIE_NAME should use the __Host- prefix in production.")
    if env_bool("CSP_REPORT_ONLY", default=False):
        errors.append("CSP_REPORT_ONLY must be false in production; enforce CSP instead of report-only mode.")
    if os.environ.get("RATE_LIMIT_BACKEND", "memory").strip().lower() == "memory":
        warnings.append("RATE_LIMIT_BACKEND=memory is acceptable for a small controlled deployment but Redis is required before serious production traffic.")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "")
    parsed = urlparse(public_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append("PUBLIC_BASE_URL must be a real HTTPS URL in production.")

for key in ["CHECKOUT_STARTER_URL", "CHECKOUT_GROWTH_URL", "CHECKOUT_SCALE_URL"]:
    value = os.environ.get(key, "")
    if not value:
        warnings.append(f"{key} is missing. Billing page will block automated checkout for that plan.")
    elif not value.startswith("https://"):
        errors.append(f"{key} must be an HTTPS URL.")

if app_env == "production":
    webhook_secret = os.environ.get("BILLING_WEBHOOK_SECRET", "")
    if not webhook_secret:
        warnings.append("BILLING_WEBHOOK_SECRET is missing. Provider webhooks will be disabled.")
    elif len(webhook_secret) < 24:
        errors.append("BILLING_WEBHOOK_SECRET must be at least 24 characters when configured.")
    platform_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")
    if not platform_password or platform_password in {"demo12345", "change-this-platform-password"} or len(platform_password) < 12:
        errors.append("PLATFORM_ADMIN_PASSWORD must be a real 12+ character password in production.")
    if not os.environ.get("PLATFORM_ADMIN_EMAIL"):
        warnings.append("PLATFORM_ADMIN_EMAIL is missing. The default demo platform email will be used.")
    if env_bool("SEED_DEMO_DATA", "ENABLE_DEMO_SEED", default=False) and os.environ.get("ALLOW_DEMO_DATA_IN_PRODUCTION", "false").lower() != "true":
        errors.append("SEED_DEMO_DATA/ENABLE_DEMO_SEED cannot be true in production unless ALLOW_DEMO_DATA_IN_PRODUCTION=true for a controlled demo environment.")
    if env_bool("SCHOOLMIND_REQUIRE_INVITES", default=False) and "ALLOW_SELF_REGISTER" in os.environ and env_bool("ALLOW_SELF_REGISTER", default=True):
        warnings.append("Both SCHOOLMIND_REQUIRE_INVITES and ALLOW_SELF_REGISTER are enabled. Public /start will stay open because ALLOW_SELF_REGISTER wins.")

for key, minimum in {"DATABASE_CONNECT_TIMEOUT_SECONDS": 1, "DATABASE_STATEMENT_TIMEOUT_MS": 1000}.items():
    if key in os.environ:
        try:
            if int(os.environ[key]) < minimum:
                errors.append(f"{key} is too low for reliable production database use.")
        except ValueError:
            errors.append(f"{key} must be an integer.")

rate_backend = os.environ.get("RATE_LIMIT_BACKEND", "memory").strip().lower()
if rate_backend not in {"memory", "redis"}:
    errors.append("RATE_LIMIT_BACKEND must be memory or redis.")

email_mode = os.environ.get("EMAIL_DELIVERY_MODE", "queue")
if email_mode not in {"queue", "console", "smtp"}:
    errors.append("EMAIL_DELIVERY_MODE must be queue, console, or smtp.")
if email_mode == "smtp" and not os.environ.get("SMTP_HOST"):
    errors.append("SMTP_HOST is required when EMAIL_DELIVERY_MODE=smtp.")

required_files = ["app.py", "wsgi.py", "render.yaml", "Procfile", "requirements.txt", "schoolmind/static/css/pixel.css"]
for item in required_files:
    if not (ROOT / item).exists():
        errors.append(f"Missing {item}")

if warnings:
    print("Warnings:")
    for warning in warnings:
        print(f"- {warning}")

if errors:
    print("Errors:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Production preflight passed.")
