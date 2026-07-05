import os
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AUTO_INIT_DB", "true")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("SECRET_KEY", "legal-trust-audit-secret")

from schoolmind import create_app

REQUIRED_PAGES = {
    "/privacy": ["Student data needs governance", "Readiness matrix", "Access and deletion requests"],
    "/terms": ["Educational support only", "Emergency boundary", "Commercial readiness"],
    "/data-processing-agreement": ["DPA draft", "Processing purpose", "Required production fields"],
    "/dpa": ["DPA draft", "Subprocessors", "Security incidents"],
    "/student-data-notice": ["Student data notice", "Who may see information", "School-owned notice"],
    "/incident-response": ["Incident response", "Response workflow", "Backup restore test"],
    "/data-retention": ["Data retention", "Default retention posture"],
    "/subprocessors": ["Subprocessors", "External services"],
}

REQUIRED_FILES = [
    "schoolmind/services/legal_trust.py",
    "schoolmind/templates/public/data_processing_agreement.html",
    "schoolmind/templates/public/student_data_notice.html",
    "schoolmind/templates/public/incident_response.html",
]

REQUIRED_MARKERS = {
    "schoolmind/services/legal_trust.py": [
        "PRIVACY_COMMITMENTS",
        "DPA_SECTIONS",
        "STUDENT_NOTICE_POINTS",
        "INCIDENT_RESPONSE_STEPS",
        "LEGAL_READINESS_MATRIX",
    ],
    "schoolmind/static/css/company.css": [
        "Phase 11 legal trust system",
        ".legal-steps",
        ".policy-section",
    ],
}


def main():
    failures = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            failures.append(f"missing file: {rel}")
    for rel, markers in REQUIRED_MARKERS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                failures.append(f"{rel} missing marker {marker!r}")
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    try:
        app = create_app({"TESTING": True, "DATABASE_PATH": tmp.name, "SECRET_KEY": "legal-trust-audit-secret"})
        client = app.test_client()
        sitemap = client.get("/sitemap.xml").data.decode("utf-8")
        footer_html = client.get("/privacy").data.decode("utf-8")
        for path, needles in REQUIRED_PAGES.items():
            response = client.get(path)
            if response.status_code != 200:
                failures.append(f"{path} returned {response.status_code}")
                continue
            html = response.data.decode("utf-8")
            for needle in needles:
                if needle not in html:
                    failures.append(f"{path} missing {needle!r}")
            if path not in sitemap and path != "/dpa":
                failures.append(f"sitemap missing {path}")
        for footer_path in ["/data-processing-agreement", "/student-data-notice", "/incident-response"]:
            if footer_path not in footer_html:
                failures.append(f"footer missing {footer_path}")
    finally:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
    if failures:
        raise SystemExit("Legal trust audit failed:\n" + "\n".join(failures))
    print(f"Legal trust audit passed: {len(REQUIRED_PAGES)} public legal pages checked.")


if __name__ == "__main__":
    main()
