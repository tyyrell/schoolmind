import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BLOCKED_SUFFIXES = {".pyc", ".pyo"}
RUNTIME_SUFFIXES = {".sqlite", ".sqlite3", ".db"}
REMOVED = []

for path in sorted(ROOT.rglob("*"), key=lambda item: len(item.parts), reverse=True):
    rel = path.relative_to(ROOT)
    if any(part in {".git", ".venv", "venv", "node_modules"} for part in rel.parts):
        continue
    if path.is_dir() and path.name in BLOCKED_DIRS:
        shutil.rmtree(path)
        REMOVED.append(str(rel))
    elif path.is_file() and path.suffix.lower() in BLOCKED_SUFFIXES:
        path.unlink()
        REMOVED.append(str(rel))
    elif path.is_file() and path.suffix.lower() in RUNTIME_SUFFIXES:
        path.unlink()
        REMOVED.append(str(rel))

if REMOVED:
    print("Cleaned release artifacts:")
    for item in REMOVED:
        print(f"- {item}")
else:
    print("No release artifacts needed cleanup.")
