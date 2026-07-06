import os
import json
import logging
import time
import uuid
from datetime import timedelta
from urllib.parse import urlparse
from flask import Flask, g, has_app_context, render_template, request, session

from .db import build_postgres_database_url, close_db, init_database, mask_database_url, normalize_database_url, postgres_url_settings, seed_demo_data
from .security import csrf_token, inject_security_context, apply_security_headers, client_ip
from .services.seo import seo_meta_for_request


def create_app(test_config=None):
    app_env = os.environ.get("APP_ENV", "development").lower()
    raw_database_url = os.environ.get("DATABASE_URL", "")
    database_engine = resolve_database_engine(os.environ.get("DATABASE_ENGINE", ""), raw_database_url)
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        APP_ENV=app_env,
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE_ENGINE=database_engine,
        DATABASE_URL=normalize_database_url(raw_database_url) if database_engine == "postgres" else raw_database_url,
        DATABASE_PATH=resolve_database_path(raw_database_url, os.environ.get("DATABASE_PATH"), app.instance_path, app_env, database_engine),
        DATABASE_SSLMODE=os.environ.get("DATABASE_SSLMODE", "require" if database_engine == "postgres" and app_env == "production" else "").strip(),
        DATABASE_CONNECT_TIMEOUT_SECONDS=env_int("DATABASE_CONNECT_TIMEOUT_SECONDS", 10),
        DATABASE_STATEMENT_TIMEOUT_MS=env_int("DATABASE_STATEMENT_TIMEOUT_MS", 30000),
        DATABASE_APPLICATION_NAME=os.environ.get("DATABASE_APPLICATION_NAME", "schoolmind-ai").strip() or "schoolmind-ai",
        DATABASE_POOLING_MODE=os.environ.get("DATABASE_POOLING_MODE", "external").strip().lower(),
        DEMO_MODE=env_bool("DEMO_MODE", default=False),
        SEED_DEMO_DATA=env_bool("SEED_DEMO_DATA", "ENABLE_DEMO_SEED", default="false" if app_env == "production" else "true"),
        ALLOW_SELF_REGISTER=env_bool("ALLOW_SELF_REGISTER", default=not env_bool("SCHOOLMIND_REQUIRE_INVITES", default=False)),
        ALLOW_SCHOOL_ADMIN_MANUAL_BILLING=env_bool("ALLOW_SCHOOL_ADMIN_MANUAL_BILLING", default=False),
        SESSION_COOKIE_NAME=os.environ.get("SESSION_COOKIE_NAME", "__Host-schoolmind_session" if app_env == "production" else "schoolmind_session"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true" if app_env == "production" else "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=4),
        MAX_CONTENT_LENGTH=1_000_000,
        PUBLIC_BASE_URL=os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000"),
        CHECKOUT_STARTER_URL=os.environ.get("CHECKOUT_STARTER_URL", ""),
        CHECKOUT_GROWTH_URL=os.environ.get("CHECKOUT_GROWTH_URL", ""),
        CHECKOUT_SCALE_URL=os.environ.get("CHECKOUT_SCALE_URL", ""),
        BILLING_WEBHOOK_SECRET=os.environ.get("BILLING_WEBHOOK_SECRET", ""),
        EMAIL_DELIVERY_MODE=os.environ.get("EMAIL_DELIVERY_MODE", "queue"),
        SMTP_HOST=os.environ.get("SMTP_HOST", ""),
        SMTP_PORT=env_int("SMTP_PORT", 587),
        SMTP_USERNAME=os.environ.get("SMTP_USERNAME", ""),
        SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
        SMTP_FROM=os.environ.get("SMTP_FROM", os.environ.get("SUPPORT_EMAIL", "support@schoolmind.ai")),
        SMTP_USE_TLS=os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
        SUPPORT_EMAIL=os.environ.get("SUPPORT_EMAIL", "support@schoolmind.ai"),
        TEST_EMAIL_RECIPIENT=os.environ.get("TEST_EMAIL_RECIPIENT", os.environ.get("SUPPORT_EMAIL", "support@schoolmind.ai")),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
        ENABLE_REQUEST_LOGGING=env_bool("ENABLE_REQUEST_LOGGING", default=True),
        REQUEST_ID_HEADER=os.environ.get("REQUEST_ID_HEADER", "X-Request-ID"),
        TRUST_PROXY_HEADERS=env_bool("TRUST_PROXY_HEADERS", default=False),
        RATE_LIMIT_BACKEND=os.environ.get("RATE_LIMIT_BACKEND", "memory").strip().lower(),
        CSP_REPORT_ONLY=env_bool("CSP_REPORT_ONLY", default=False),
        CSP_REPORT_URI=os.environ.get("CSP_REPORT_URI", "").strip(),
    )
    if test_config:
        app.config.update(test_config)
        if app.config.get("APP_ENV") == "production" and "SESSION_COOKIE_NAME" not in test_config and not os.environ.get("SESSION_COOKIE_NAME"):
            app.config["SESSION_COOKIE_NAME"] = "__Host-schoolmind_session"
        app.config["DATABASE_ENGINE"] = normalize_database_engine(app.config.get("DATABASE_ENGINE", app.config.get("DATABASE_URL", "") and resolve_database_engine("", app.config.get("DATABASE_URL", "")) or database_engine))
        if app.config.get("DATABASE_ENGINE") == "postgres":
            app.config["DATABASE_URL"] = normalize_database_url(app.config.get("DATABASE_URL", ""))
            if not app.config.get("DATABASE_SSLMODE") and app.config.get("APP_ENV") == "production":
                app.config["DATABASE_SSLMODE"] = "require"
            app.config.setdefault("DATABASE_CONNECT_TIMEOUT_SECONDS", 10)
            app.config.setdefault("DATABASE_STATEMENT_TIMEOUT_MS", 30000)
            app.config.setdefault("DATABASE_APPLICATION_NAME", "schoolmind-ai")
            app.config.setdefault("DATABASE_POOLING_MODE", "external")
    if app.config.get("TESTING"):
        app.config["ENABLE_REQUEST_LOGGING"] = False

    configure_logging(app)
    validate_database_config(app)
    validate_runtime_config(app)
    enforce_production_safety(app)

    os.makedirs(app.instance_path, exist_ok=True)

    @app.before_request
    def make_session_permanent():
        g.request_id = request.headers.get(app.config["REQUEST_ID_HEADER"]) or secretsafe_request_id()
        g.request_started_at = time.perf_counter()
        session.permanent = True
        csrf_token()
        # Persist language selection from a site cookie if present.
        try:
            lang_cookie = request.cookies.get("site_language")
            if lang_cookie and not session.get("language"):
                session["language"] = lang_cookie
        except Exception:
            pass

    app.teardown_appcontext(close_db)
    app.context_processor(inject_security_context)

    @app.context_processor
    def inject_seo_context():
        try:
            language = session.get("language", "en")
            return {"seo_meta": seo_meta_for_request(language)}
        except Exception:
            return {"seo_meta": {
                "title": "SchoolMind AI",
                "description": "SchoolMind AI",
                "keywords": "SchoolMind AI",
                "robots": "noindex, nofollow",
                "canonical": request.base_url,
                "alternates": {"en": request.base_url, "ar": request.base_url + "?language=ar", "x-default": request.base_url},
                "og_title": "SchoolMind AI",
                "og_description": "SchoolMind AI",
                "og_type": "website",
                "og_url": request.base_url,
                "og_image": "",
                "locale": "en_US",
                "alternate_locale": "ar_AR",
                "twitter_title": "SchoolMind AI",
                "twitter_description": "SchoolMind AI",
                "twitter_image": "",
                "structured_data": [],
            }}

    app.after_request(apply_security_headers)

    @app.after_request
    def log_request(response):
        request_id = getattr(g, "request_id", secretsafe_request_id())
        response.headers.setdefault(app.config["REQUEST_ID_HEADER"], request_id)
        if app.config.get("ENABLE_REQUEST_LOGGING"):
            elapsed_ms = round((time.perf_counter() - getattr(g, "request_started_at", time.perf_counter())) * 1000, 2)
            app.logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "remote_addr": client_ip(),
                },
            )
        return response

    from .public import bp as public_bp
    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp
    from .api import bp as api_bp
    from .platform import bp as platform_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(platform_bp)

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/error.html", code=400, title="Bad request", message="The request was rejected."), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/error.html", code=403, title="Forbidden", message="This workspace area is not available for your role."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", code=404, title="Not found", message="The page or record does not exist."), 404

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template("errors/error.html", code=429, title="Too many requests", message="Slow down and try again later."), 429

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("unhandled_server_error", extra={"request_id": getattr(g, "request_id", "")})
        return render_template("errors/error.html", code=500, title="Server error", message="The server hit an unexpected problem."), 500

    @app.cli.command("init-db")
    def init_db_command():
        init_database()
        print("Database initialized.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        init_database()
        seed_demo_data()
        print("Demo data seeded.")

    if os.environ.get("AUTO_INIT_DB", "true").lower() == "true":
        with app.app_context():
            init_database()
            if should_seed_demo_data(app):
                seed_demo_data()

    # Graceful shutdown handling for proper resource cleanup
    def shutdown_handler(signum, frame):
        """Handle shutdown signals gracefully without swallowing process termination."""
        app.logger.info("shutdown_signal_received", extra={"signal": signum})
        if has_app_context():
            close_db()
        raise SystemExit(0)
    
    if not app.config.get("TESTING"):
        import signal
        try:
            signal.signal(signal.SIGTERM, shutdown_handler)
            signal.signal(signal.SIGINT, shutdown_handler)
        except ValueError:
            app.logger.debug("shutdown_signal_registration_skipped")

    return app


def normalize_database_engine(value):
    normalized = str(value or "").strip().lower()
    aliases = {"postgresql": "postgres", "pg": "postgres", "sqlite3": "sqlite"}
    return aliases.get(normalized, normalized)


def resolve_database_engine(database_engine=None, database_url=""):
    explicit = normalize_database_engine(database_engine)
    if explicit:
        return explicit
    value = (database_url or "").strip().lower()
    if value.startswith(("postgres://", "postgresql://")):
        return "postgres"
    return "sqlite"


def resolve_database_path(database_url, database_path, instance_path, app_env="development", database_engine="sqlite"):
    engine = normalize_database_engine(database_engine)
    value = (database_url or "").strip()
    if engine == "postgres":
        return database_path or ""
    if value.startswith("sqlite:///"):
        return value.replace("sqlite:///", "", 1)
    if value.startswith("sqlite://"):
        return value.replace("sqlite://", "", 1)
    return database_path or os.path.join(instance_path, "schoolmind.sqlite3")


def validate_database_config(app):
    engine = normalize_database_engine(app.config.get("DATABASE_ENGINE", "sqlite"))
    app.config["DATABASE_ENGINE"] = engine
    database_url = str(app.config.get("DATABASE_URL", "") or "").strip()
    app_env = str(app.config.get("APP_ENV", "development")).lower()
    allow_sqlite_production = env_bool("ALLOW_SQLITE_IN_PRODUCTION", default=False) or app_env == "demo" or app.config.get("DEMO_MODE")

    if engine not in {"sqlite", "postgres"}:
        raise RuntimeError("DATABASE_ENGINE must be sqlite or postgres.")
    if database_url.lower().startswith(("postgres://", "postgresql://")) and engine != "postgres":
        raise RuntimeError("DATABASE_URL is PostgreSQL, but DATABASE_ENGINE is not postgres. Refusing to silently run SQLite.")
    if engine == "postgres":
        if not database_url:
            raise RuntimeError("DATABASE_ENGINE=postgres requires DATABASE_URL.")
        if not database_url.lower().startswith(("postgres://", "postgresql://")):
            raise RuntimeError("DATABASE_URL must start with postgres:// or postgresql:// when DATABASE_ENGINE=postgres.")
        sslmode = str(app.config.get("DATABASE_SSLMODE", "") or "").strip().lower()
        if sslmode not in {"", "disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise RuntimeError("DATABASE_SSLMODE must be disable, allow, prefer, require, verify-ca, verify-full, or blank.")
        if app.config.get("APP_ENV") == "production" and sslmode in {"", "disable", "allow", "prefer"}:
            raise RuntimeError("Production PostgreSQL requires DATABASE_SSLMODE=require, verify-ca, or verify-full.")
        pool_mode = str(app.config.get("DATABASE_POOLING_MODE", "external") or "external").strip().lower()
        if pool_mode not in {"external", "direct", "transaction", "session"}:
            raise RuntimeError("DATABASE_POOLING_MODE must be external, direct, transaction, or session.")
        try:
            app.config["DATABASE_CONNECT_TIMEOUT_SECONDS"] = int(app.config.get("DATABASE_CONNECT_TIMEOUT_SECONDS", 10))
            app.config["DATABASE_STATEMENT_TIMEOUT_MS"] = int(app.config.get("DATABASE_STATEMENT_TIMEOUT_MS", 30000))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("DATABASE_CONNECT_TIMEOUT_SECONDS and DATABASE_STATEMENT_TIMEOUT_MS must be integers.") from exc
        if app.config["DATABASE_CONNECT_TIMEOUT_SECONDS"] < 1 or app.config["DATABASE_STATEMENT_TIMEOUT_MS"] < 1000:
            raise RuntimeError("Database timeout settings are too low for reliable production use.")
        app.config["DATABASE_URL"] = build_postgres_database_url(
            database_url,
            sslmode=sslmode,
            application_name=app.config.get("DATABASE_APPLICATION_NAME", "schoolmind-ai"),
        )
    if engine == "sqlite":
        if app_env == "production" and not allow_sqlite_production:
            raise RuntimeError("Production requires DATABASE_ENGINE=postgres. Set ALLOW_SQLITE_IN_PRODUCTION=true only for a controlled demo exception.")
        if not app.config.get("DATABASE_PATH"):
            raise RuntimeError("DATABASE_ENGINE=sqlite requires DATABASE_PATH.")


def should_seed_demo_data(app):
    default_seed = "false" if app.config.get("APP_ENV") == "production" else "true"
    requested = env_bool("SEED_DEMO_DATA", "ENABLE_DEMO_SEED", default=default_seed)
    if not requested:
        return False
    if app.config.get("APP_ENV") == "production" and os.environ.get("ALLOW_DEMO_DATA_IN_PRODUCTION", "false").lower() != "true":
        raise RuntimeError("Refusing to seed demo data in production without ALLOW_DEMO_DATA_IN_PRODUCTION=true.")
    return True


def configure_logging(app):
    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING if app.config.get("APP_ENV") == "production" else logging.INFO)


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        message = mask_log_value(record.getMessage())
        payload = {
            "level": record.levelname,
            "message": message,
            "logger": record.name,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        for key in ("request_id", "method", "path", "status_code", "elapsed_ms", "remote_addr"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = mask_log_value(value)
        if record.exc_info:
            payload["exception"] = mask_log_value(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def mask_log_value(value):
    text = str(value)
    text = re_mask_database_urls(text)
    return text


def re_mask_database_urls(text):
    import re
    pattern = re.compile(r"postgres(?:ql)?://[^\s'\"<>]+", re.IGNORECASE)
    return pattern.sub(lambda match: mask_database_url(match.group(0)), text)


def validate_runtime_config(app):
    mode = app.config.get("EMAIL_DELIVERY_MODE", "queue")
    if mode not in {"queue", "console", "smtp"}:
        raise RuntimeError("EMAIL_DELIVERY_MODE must be queue, console, or smtp.")
    if app.config.get("RATE_LIMIT_BACKEND") not in {"memory", "redis"}:
        raise RuntimeError("RATE_LIMIT_BACKEND must be memory or redis.")
    if app.config.get("APP_ENV") != "production":
        return
    public_base_url = app.config.get("PUBLIC_BASE_URL", "")
    parsed_public_url = urlparse(public_base_url)
    if parsed_public_url.scheme != "https" or not parsed_public_url.netloc:
        raise RuntimeError("PUBLIC_BASE_URL must be a real HTTPS URL in production.")
    if not app.config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError("SESSION_COOKIE_SECURE must be true in production.")
    if not str(app.config.get("SESSION_COOKIE_NAME", "")).startswith("__Host-"):
        raise RuntimeError("SESSION_COOKIE_NAME should use the __Host- prefix in production.")
    if app.config.get("CSP_REPORT_ONLY"):
        raise RuntimeError("CSP_REPORT_ONLY must be false in production; use enforce mode.")
    if app.config.get("RATE_LIMIT_BACKEND") == "memory":
        app.logger.warning("rate_limit_memory_backend_in_production", extra={"request_id": "startup"})
    db_settings = postgres_url_settings(app.config.get("DATABASE_URL", "")) if app.config.get("DATABASE_ENGINE") == "postgres" else {}
    sslmode = str(app.config.get("DATABASE_SSLMODE") or db_settings.get("sslmode") or "").lower()
    if app.config.get("DATABASE_ENGINE") == "postgres" and sslmode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("Production PostgreSQL must enforce TLS with DATABASE_SSLMODE=require or stronger.")
    webhook_secret = app.config.get("BILLING_WEBHOOK_SECRET", "")
    if webhook_secret and len(webhook_secret) < 24:
        raise RuntimeError("BILLING_WEBHOOK_SECRET must be at least 24 characters when configured.")
    if mode == "smtp" and (not app.config.get("SMTP_HOST") or not app.config.get("SMTP_FROM")):
        raise RuntimeError("SMTP_HOST and SMTP_FROM are required when EMAIL_DELIVERY_MODE=smtp.")
    smtp_from = app.config.get("SMTP_FROM", "")
    if smtp_from and "@" not in smtp_from:
        raise RuntimeError("SMTP_FROM must be a valid email address when configured.")
    test_recipient = app.config.get("TEST_EMAIL_RECIPIENT", "")
    if test_recipient and "@" not in test_recipient:
        raise RuntimeError("TEST_EMAIL_RECIPIENT must be a valid email address when configured.")
    for key in ("CHECKOUT_STARTER_URL", "CHECKOUT_GROWTH_URL", "CHECKOUT_SCALE_URL"):
        value = app.config.get(key, "")
        if value and urlparse(value).scheme != "https":
            raise RuntimeError(f"{key} must be HTTPS when configured.")


def enforce_production_safety(app):
    if app.config.get("APP_ENV") != "production":
        return
    
    # Validate SECRET_KEY
    secret = app.config.get("SECRET_KEY", "")
    if not secret or secret == "dev-only-change-me" or len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be a real 32+ character secret in production.")
    
    # Validate PLATFORM_ADMIN_PASSWORD
    platform_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")
    if not platform_password or platform_password in {"demo12345", "change-this-platform-password"} or len(platform_password) < 12:
        raise RuntimeError("PLATFORM_ADMIN_PASSWORD must be a real 12+ character password in production.")
    
    # Validate required environment variables
    required_vars = {
        "PLATFORM_ADMIN_EMAIL": "Platform admin email for SaaS operator",
        "DATABASE_URL": "PostgreSQL connection string",
    }
    
    missing = [f"{k}: {v}" for k, v in required_vars.items() if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables in production:\n  - " + "\n  - ".join(missing))
    
    # Validate DATABASE_ENGINE is postgres in production
    if app.config.get("DATABASE_ENGINE") != "postgres":
        raise RuntimeError("DATABASE_ENGINE must be 'postgres' in production (not sqlite).")
    
    # Warn about demo data
    if env_bool("SEED_DEMO_DATA", "ENABLE_DEMO_SEED", default=False) and os.environ.get("ALLOW_DEMO_DATA_IN_PRODUCTION", "false").lower() != "true":
        raise RuntimeError("SEED_DEMO_DATA cannot be true in production unless ALLOW_DEMO_DATA_IN_PRODUCTION=true.")
    
    # Validate payment configuration if payments enabled
    checkout_urls = [
        app.config.get("CHECKOUT_STARTER_URL"),
        app.config.get("CHECKOUT_GROWTH_URL"),
        app.config.get("CHECKOUT_SCALE_URL"),
    ]
    if any(checkout_urls):  # If any checkout URL is configured
        if not app.config.get("BILLING_WEBHOOK_SECRET"):
            raise RuntimeError("BILLING_WEBHOOK_SECRET is required when any CHECKOUT_*_URL is configured.")


def env_bool(*names, default=False):
    for name in names:
        if name in os.environ:
            return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, str):
        return default.strip().lower() in {"1", "true", "yes", "on"}
    return bool(default)


def env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def secretsafe_request_id():
    return uuid.uuid4().hex
