"""Audit bilingual public-site readiness for SchoolMind AI."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AUTO_INIT_DB", "true")
os.environ.setdefault("SEED_DEMO_DATA", "true")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schoolmind import create_app  # noqa: E402
REQUIRED_TEMPLATE_MARKERS = [
    "t('home.hero.title')",
    "t('home.problem.title')",
    "t('home.workflow.title')",
    "t('home.roles.title')",
    "t('home.trust.title')",
    "t('home.final.title')",
]


def main() -> int:
    index_template = (ROOT / "schoolmind" / "templates" / "public" / "index.html").read_text(encoding="utf-8")
    base_template = (ROOT / "schoolmind" / "templates" / "base.html").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in index_template]
    if missing:
        raise SystemExit(f"Missing translated homepage markers: {missing}")
    if "language-switcher" not in base_template or "language_url('ar')" not in base_template:
        raise SystemExit("Base template is missing persistent language switcher links.")

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    try:
        app = create_app({"TESTING": True, "DATABASE_PATH": tmp.name, "SECRET_KEY": "test-secret", "ALLOW_SELF_REGISTER": True})
        client = app.test_client()
        en = client.get("/")
        ar = client.get("/?language=ar")
        if en.status_code != 200 or ar.status_code != 200:
            raise SystemExit("Public homepage did not load in both languages.")
        en_html = en.data.decode("utf-8")
        ar_html = ar.data.decode("utf-8")
        if 'lang="en"' not in en_html or 'dir="ltr"' not in en_html:
            raise SystemExit("English homepage is not marked LTR correctly.")
        if 'lang="ar"' not in ar_html or 'dir="rtl"' not in ar_html:
            raise SystemExit("Arabic homepage is not marked RTL correctly.")
        for needle in ["ساعد كل مدرسة", "جرّب قبل التسجيل", "الخصوصية والسلامة"]:
            if needle not in ar_html:
                raise SystemExit(f"Arabic homepage missing translated copy: {needle}")
        if "Schools do not need more scattered forms" not in en_html:
            raise SystemExit("English homepage lost its core buyer-problem copy.")
    finally:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
    print("I18n audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
