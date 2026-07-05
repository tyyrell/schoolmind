import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "schoolmind_pixel_saas_SUPABASE_POSTGRES_READY.zip"
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "instance"}
EXCLUDE_FILES = {".env"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log"}


def run(command, env=None):
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT, env=env or os.environ.copy(), text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDE_FILES:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return path.is_file()


def count_tests() -> int:
    test_file = ROOT / "run_tests.py"
    return test_file.read_text(encoding="utf-8").count("def test_")


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output = output.resolve()

    run([sys.executable, "-m", "compileall", "-q", "."])
    run([sys.executable, "run_tests.py"])
    run([sys.executable, "scripts/audit.py"])

    preflight_env = os.environ.copy()
    preflight_env.update(
        {
            "APP_ENV": "production",
            "SESSION_COOKIE_SECURE": "true",
            "SECRET_KEY": "release-check-secret-key-please-change-123456",
            "PUBLIC_BASE_URL": "https://schoolmind.example.com",
            "DATABASE_ENGINE": "postgres",
            "DATABASE_URL": "postgresql://user:password@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require",
            "CHECKOUT_STARTER_URL": "https://checkout.example.com/starter",
            "CHECKOUT_GROWTH_URL": "https://checkout.example.com/growth",
            "CHECKOUT_SCALE_URL": "https://checkout.example.com/scale",
            "PLATFORM_ADMIN_EMAIL": "owner@example.com",
            "PLATFORM_ADMIN_PASSWORD": "ReleaseCheckPassword123!",
            "BILLING_WEBHOOK_SECRET": "release-check-webhook-secret-change-me",
            "SEED_DEMO_DATA": "false",
            "ENABLE_DEMO_SEED": "false",
            "DEMO_MODE": "false",
            "ALLOW_SELF_REGISTER": "false",
            "SCHOOLMIND_REQUIRE_INVITES": "true",
            "ALLOW_DEMO_DATA_IN_PRODUCTION": "false",
        }
    )
    run([sys.executable, "scripts/preflight.py"], env=preflight_env)
    run([sys.executable, "scripts/route_audit.py"])
    run([sys.executable, "scripts/action_integrity.py"])
    run([sys.executable, "scripts/i18n_report.py"])
    run([sys.executable, "scripts/clean_release.py"])
    run([sys.executable, "scripts/release_check.py"])

    if output.exists():
        output.unlink()

    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT.parent))

    manifest = {
        "artifact": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": ROOT.name,
        "file_count": len(files),
        "test_count": count_tests(),
        "route_audit_endpoints": 84,
        "release_status": "supabase-postgres-ready SaaS build with explicit database engine selection, PostgreSQL adapter, schema migrations, mobile polish, action integrity, personalization onboarding, Nour chat, billing, and progress reporting",
        "excluded_dirs": sorted(EXCLUDE_DIRS),
        "excluded_suffixes": sorted(EXCLUDE_SUFFIXES),
    }
    manifest_path = ROOT / "docs" / "FINAL_RELEASE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Rebuild once so the manifest is inside the ZIP.
    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT.parent))

    print(f"Release package created: {output}")
    print(f"Packaged files: {len(files)}")


if __name__ == "__main__":
    main()
