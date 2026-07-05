import os
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AUTO_INIT_DB", "true")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("SECRET_KEY", "company-site-audit-secret")

from schoolmind import create_app

REQUIRED_PAGES = {
    "/product": ["Product overview", "Core modules", "School governance"],
    "/features": ["Features", "Nour AI-assisted companion", "Admin operations"],
    "/human-review": ["Human review", "The school must decide", "Human action"],
    "/compliance": ["Compliance overview", "No fake badges", "Formal compliance claims"],
    "/cookies": ["Cookie policy", "No default ad tracking", "Required session cookie"],
    "/request-demo": ["Request demo", "Standard monthly", "Send demo request"],
}


def main():
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    try:
        app = create_app({"TESTING": True, "DATABASE_PATH": tmp.name, "SECRET_KEY": "company-site-audit-secret"})
        client = app.test_client()
        failures = []
        for path, needles in REQUIRED_PAGES.items():
            response = client.get(path)
            if response.status_code != 200:
                failures.append(f"{path} returned {response.status_code}")
                continue
            html = response.data.decode("utf-8")
            for needle in needles:
                if needle not in html:
                    failures.append(f"{path} missing: {needle}")
        sitemap = client.get("/sitemap.xml").data.decode("utf-8")
        for path in REQUIRED_PAGES:
            if path not in sitemap:
                failures.append(f"sitemap missing {path}")
        if failures:
            raise SystemExit("Company site audit failed:\n" + "\n".join(failures))
        report = ["# Company Site Audit", "", "Required official company pages are present and discoverable.", ""]
        for path in REQUIRED_PAGES:
            report.append(f"- `{path}`")
        (ROOT / "docs" / "COMPANY_SITE_AUDIT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        print(f"Company site audit passed: {len(REQUIRED_PAGES)} official pages checked.")
    finally:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
