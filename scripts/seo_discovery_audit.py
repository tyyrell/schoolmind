import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []

base = (ROOT / "schoolmind" / "templates" / "base.html").read_text(encoding="utf-8")
seo_service = (ROOT / "schoolmind" / "services" / "seo.py").read_text(encoding="utf-8")
public_py = (ROOT / "schoolmind" / "public.py").read_text(encoding="utf-8")
security_py = (ROOT / "schoolmind" / "security.py").read_text(encoding="utf-8")

required_base_markers = [
    "seo_meta.description",
    "seo_meta.canonical",
    "hreflang=\"en\"",
    "hreflang=\"ar\"",
    "hreflang=\"x-default\"",
    "property=\"og:url\"",
    "property=\"og:image\"",
    "name=\"twitter:image\"",
    "application/ld+json",
    "nonce=\"{{ csp_nonce() }}\"",
]
for marker in required_base_markers:
    if marker not in base:
        errors.append(f"Missing base SEO marker: {marker}")

required_service_markers = [
    "PAGE_SEO",
    "sitemap_entries",
    "Organization",
    "SoftwareApplication",
    "FAQPage",
    "BreadcrumbList",
    "x-default",
    "max-image-preview:large",
]
for marker in required_service_markers:
    if marker not in seo_service:
        errors.append(f"Missing SEO service marker: {marker}")

required_public_markers = [
    "@bp.route(\"/sitemap.xml\")",
    "xmlns:xhtml",
    "<lastmod>",
    "<changefreq>",
    "<priority>",
    "@bp.route(\"/robots.txt\")",
    "Disallow: /api/",
    "@bp.route(\"/humans.txt\")",
    "@bp.route(\"/llms.txt\")",
]
for marker in required_public_markers:
    if marker not in public_py:
        errors.append(f"Missing discovery route marker: {marker}")

if "current_csp_nonce" not in security_py or "nonce-{current_csp_nonce()}" not in security_py:
    errors.append("CSP nonce support is missing for JSON-LD structured data.")

page_paths = re.findall(r'"path": "([^"]+)"', seo_service)
if len(set(page_paths)) < 20:
    errors.append("SEO page registry is too small for the public company site.")

if errors:
    print("SEO discovery audit failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("SEO discovery audit passed")
