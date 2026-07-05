from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
checks = []
errors = []


def require(path, *needles):
    file_path = ROOT / path
    if not file_path.exists():
        errors.append(f"Missing {path}")
        return ""
    text = file_path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            errors.append(f"{path} missing {needle}")
    return text


db = require(
    "schoolmind/db.py",
    "build_postgres_database_url",
    "postgres_url_settings",
    "DATABASE_STATEMENT_TIMEOUT_MS",
    "DATABASE_CONNECT_TIMEOUT_SECONDS",
    "sslmode",
    "statement_timeout",
    "2026-07-schoolmind-postgres-14",
)
require(
    "schoolmind/__init__.py",
    "DATABASE_SSLMODE",
    "DATABASE_POOLING_MODE",
    "Production PostgreSQL requires DATABASE_SSLMODE=require",
    "build_postgres_database_url",
)
require(
    "schoolmind/services/database_ops.py",
    "postgres_runtime_settings",
    "PRODUCTION_DATABASE_ENV_VARS",
    "PostgreSQL TLS",
    "Connection pooling posture",
)
require(
    "schoolmind/templates/dashboard/database.html",
    "Supabase/PostgreSQL readiness",
    "Masked DATABASE_URL",
    "Production database inputs",
)
require(
    "scripts/preflight.py",
    "DATABASE_SSLMODE",
    "DATABASE_POOLING_MODE",
    "sslmode=require",
)
require(
    ".env.example",
    "DATABASE_SSLMODE",
    "DATABASE_POOLING_MODE",
    "DATABASE_STATEMENT_TIMEOUT_MS",
)
require(
    "render.yaml",
    "DATABASE_SSLMODE",
    "DATABASE_POOLING_MODE",
    "DATABASE_STATEMENT_TIMEOUT_MS",
)
require(
    "docs/phases/PHASE_14_DATABASE_PRODUCTION.md",
    "Supabase/PostgreSQL readiness",
    "Not done by code",
    "Production inputs required from owner",
)

schema = re.search(r'SCHEMA_VERSION\s*=\s*"([^"]+)"', db)
if not schema or not schema.group(1).endswith("postgres-14"):
    errors.append("SCHEMA_VERSION was not advanced for phase 14.")

if errors:
    print("PostgreSQL readiness audit failed:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("PostgreSQL readiness audit passed")
