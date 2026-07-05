import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []

security_py = (ROOT / "schoolmind" / "security.py").read_text(encoding="utf-8")
init_py = (ROOT / "schoolmind" / "__init__.py").read_text(encoding="utf-8")
public_py = (ROOT / "schoolmind" / "public.py").read_text(encoding="utf-8")
dashboard_py = (ROOT / "schoolmind" / "dashboard.py").read_text(encoding="utf-8")

required_security_markers = [
    "def safe_redirect(",
    "def safe_referrer_redirect(",
    "def build_content_security_policy(",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "Cross-Origin-Resource-Policy",
    "X-Permitted-Cross-Domain-Policies",
    "Origin-Agent-Cluster",
    "no-store, max-age=0",
    "TRUST_PROXY_HEADERS",
]
for marker in required_security_markers:
    if marker not in security_py:
        errors.append(f"Missing security marker: {marker}")

for forbidden in ["'unsafe-inline'", 'unsafe-inline', "'unsafe-eval'", 'unsafe-eval']:
    if forbidden in security_py:
        errors.append(f"Forbidden CSP token in security.py: {forbidden}")

if 'SESSION_COOKIE_NAME=os.environ.get("SESSION_COOKIE_NAME", "__Host-schoolmind_session"' not in init_py:
    errors.append("Production session cookie name is not using the __Host- default.")
if "RATE_LIMIT_BACKEND" not in init_py:
    errors.append("RATE_LIMIT_BACKEND config is missing.")
if "CSP_REPORT_ONLY" not in init_py or "CSP_REPORT_URI" not in init_py:
    errors.append("CSP report configuration is missing.")

for source_name, source in {"public.py": public_py, "dashboard.py": dashboard_py}.items():
    if "redirect(request.referrer" in source:
        errors.append(f"Unsafe request.referrer redirect remains in {source_name}.")

scan_roots = [ROOT / "schoolmind" / "templates"]
inline_style_re = re.compile(r"\sstyle\s*=", re.IGNORECASE)
inline_event_re = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
javascript_url_re = re.compile(r"javascript\s*:", re.IGNORECASE)
for scan_root in scan_roots:
    for path in scan_root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if inline_style_re.search(text):
            errors.append(f"Inline style attribute found: {path.relative_to(ROOT)}")
        if inline_event_re.search(text):
            errors.append(f"Inline event handler found: {path.relative_to(ROOT)}")
        if javascript_url_re.search(text):
            errors.append(f"javascript: URL found: {path.relative_to(ROOT)}")

if errors:
    print("Security hardening audit failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Security hardening audit passed")
