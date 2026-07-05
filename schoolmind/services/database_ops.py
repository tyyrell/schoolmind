from pathlib import Path
from urllib.parse import urlparse
from flask import current_app

from ..db import SCHEMA_VERSION, mask_database_url, postgres_url_settings, query_one

WORKSPACE_TABLES = (
    ("users", True),
    ("user_preferences", False),
    ("journal_entries", True),
    ("checkins", True),
    ("wellbeing_assessments", True),
    ("student_support_plans", True),
    ("student_goals", True),
    ("game_scores", True),
    ("breathing_sessions", True),
    ("student_ai_messages", True),
    ("risk_events", True),
    ("support_requests", True),
    ("interventions", True),
    ("case_actions", True),
    ("consent_records", True),
    ("coupon_redemptions", True),
    ("payment_intents", True),
    ("agreement_acceptances", True),
    ("billing_events", True),
    ("audit_events", True),
    ("outbox_messages", True),
    ("invite_tokens", True),
    ("password_reset_tokens", True),
    ("school_settings", True),
    ("subscriptions", True),
    ("schools", False),
    ("coupon_codes", False),
    ("site_settings", False),
    ("platform_admins", False),
    ("platform_admin_preferences", False),
    ("sales_leads", False),
    ("playbooks", False),
    ("schema_migrations", False),
)


PRODUCTION_DATABASE_ENV_VARS = (
    "DATABASE_ENGINE",
    "DATABASE_URL",
    "DATABASE_SSLMODE",
    "DATABASE_POOLING_MODE",
    "DATABASE_CONNECT_TIMEOUT_SECONDS",
    "DATABASE_STATEMENT_TIMEOUT_MS",
    "DATABASE_APPLICATION_NAME",
    "AUTO_INIT_DB",
    "SEED_DEMO_DATA",
)


def postgres_runtime_settings(database_url):
    parsed = urlparse(database_url or "")
    params = postgres_url_settings(database_url)
    host = parsed.hostname or ""
    port = parsed.port
    return {
        "host": host,
        "port": port,
        "database": parsed.path.lstrip("/") if parsed.path else "",
        "sslmode": params.get("sslmode", current_app.config.get("DATABASE_SSLMODE", "")),
        "application_name": params.get("application_name", current_app.config.get("DATABASE_APPLICATION_NAME", "schoolmind-ai")),
        "looks_like_supabase": "supabase" in host.lower(),
        "looks_like_pooler": port == 6543 or "pooler" in host.lower(),
        "pooling_mode": current_app.config.get("DATABASE_POOLING_MODE", "external"),
        "connect_timeout_seconds": current_app.config.get("DATABASE_CONNECT_TIMEOUT_SECONDS", 10),
        "statement_timeout_ms": current_app.config.get("DATABASE_STATEMENT_TIMEOUT_MS", 30000),
    }


def database_runtime_report():
    path = current_app.config.get("DATABASE_PATH", "")
    database_url = current_app.config.get("DATABASE_URL", "")
    engine = current_app.config.get("DATABASE_ENGINE", "sqlite")
    app_env = current_app.config.get("APP_ENV", "development")
    path_obj = Path(path) if engine == "sqlite" and path and path != ":memory:" else None
    parent = path_obj.parent if path_obj else None
    exists = path_obj.exists() if path_obj else engine == "postgres" or path == ":memory:"
    size_bytes = path_obj.stat().st_size if path_obj and path_obj.exists() else 0
    postgres_settings = postgres_runtime_settings(database_url) if engine == "postgres" else {}
    persistent_hint = engine == "postgres" or bool(path and (path.startswith("/var/data/") or path.startswith("/mnt/data/") or path.startswith("/data/")))
    database_ok = True
    database_detail = "Application can query the configured database."
    try:
        query_one("SELECT 1 AS ok")
    except Exception:
        database_ok = False
        database_detail = "Database query failed. Check DATABASE_ENGINE and credentials without exposing secrets."

    production_sqlite = app_env == "production" and engine == "sqlite"
    sslmode = postgres_settings.get("sslmode", "")
    tls_ready = engine != "postgres" or sslmode in {"require", "verify-ca", "verify-full"}
    pooling_ready = engine != "postgres" or postgres_settings.get("pooling_mode") in {"external", "transaction", "session", "direct"}
    migration_ready = bool(SCHEMA_VERSION and query_one("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)))
    demo_seed_safe = not (app_env == "production" and current_app.config.get("SEED_DEMO_DATA"))
    checks = [
        {
            "name": "Database connection",
            "status": "pass" if database_ok else "blocker",
            "detail": database_detail,
        },
        {
            "name": "Schema version",
            "status": "pass" if migration_ready else "blocker",
            "detail": SCHEMA_VERSION if migration_ready else f"{SCHEMA_VERSION} has not been recorded in schema_migrations.",
        },
        {
            "name": "Production database engine",
            "status": "pass" if engine == "postgres" or not production_sqlite else "blocker",
            "detail": "Production uses Supabase/PostgreSQL. SQLite is only for local, tests, or explicit demos.",
        },
        {
            "name": "PostgreSQL TLS",
            "status": "pass" if tls_ready else "blocker",
            "detail": "PostgreSQL production connections must use sslmode=require or stronger.",
        },
        {
            "name": "Connection pooling posture",
            "status": "pass" if pooling_ready else "warn",
            "detail": "Use Supabase transaction/session pooler or another external pool before serious traffic.",
        },
        {
            "name": "Persistent storage",
            "status": "pass" if app_env != "production" or persistent_hint else "warn",
            "detail": "PostgreSQL is managed externally. SQLite requires a persistent disk and is not the default production path.",
        },
        {
            "name": "Demo data in production",
            "status": "pass" if demo_seed_safe else "blocker",
            "detail": "SEED_DEMO_DATA must remain false in production unless this is an isolated demo deployment.",
        },
        {
            "name": "Backup discipline",
            "status": "pass",
            "detail": "Workspace JSON export remains available; Supabase project backups and restore drills are still required.",
        },
    ]
    return {
        "engine": engine,
        "path": path if engine == "sqlite" else "managed-postgres",
        "exists": exists,
        "size_bytes": size_bytes,
        "parent": str(parent) if parent else ("supabase" if engine == "postgres" else "memory"),
        "app_env": app_env,
        "database_url_present": bool(database_url),
        "database_url_safe": mask_database_url(database_url),
        "postgres_requested": engine == "postgres",
        "postgres_settings": postgres_settings,
        "persistent_hint": persistent_hint,
        "production_env_vars": PRODUCTION_DATABASE_ENV_VARS,
        "checks": checks,
    }


def database_table_counts(school_id=None):
    rows = []
    for table, has_school_id in WORKSPACE_TABLES:
        if school_id is not None and has_school_id:
            total = query_one(f"SELECT COUNT(*) AS c FROM {table} WHERE school_id = ?", (school_id,))["c"]
        else:
            total = query_one(f"SELECT COUNT(*) AS c FROM {table}")["c"]
        rows.append({"table": table, "total": total, "scoped": has_school_id})
    return rows


def release_safety_checks(root_path):
    root = Path(root_path)
    blocked_suffixes = {".pyc", ".sqlite", ".sqlite3", ".db"}
    blocked_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    findings = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in blocked_dirs for part in rel.parts):
            findings.append({"path": str(rel), "issue": "runtime cache directory"})
            continue
        if path.is_file() and path.suffix.lower() in blocked_suffixes:
            findings.append({"path": str(rel), "issue": "runtime database/cache artifact"})
    return findings
