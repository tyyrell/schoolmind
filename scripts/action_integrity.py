import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "schoolmind" / "templates"
STATIC_ROOT = ROOT / "schoolmind" / "static"

findings = []
for path in list(TEMPLATE_ROOT.rglob("*.html")) + list(STATIC_ROOT.rglob("*.js")):
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    for marker in ('href="#"', "href='#'", 'href=""', "onclick="):
        if marker in text:
            findings.append(f"{rel}: unsupported action marker {marker}")
    for match in re.finditer(r"<button\b([^>]*)>", text):
        attrs = match.group(1)
        if "type=" not in attrs:
            line = text[: match.start()].count("\n") + 1
            findings.append(f"{rel}:{line}: button missing explicit type")
    for match in re.finditer(r"class=\"[^\"]*clickable[^\"]*\"", text):
        tag_start = text.rfind("<", 0, match.start())
        tag_end = text.find(">", match.end())
        tag = text[tag_start : tag_end + 1]
        if "<a " not in tag and "data-" not in tag:
            line = text[: match.start()].count("\n") + 1
            findings.append(f"{rel}:{line}: clickable styling without link or JS data hook")

if findings:
    print("Action integrity failed:")
    for item in findings:
        print(f"- {item}")
    sys.exit(1)

print("Action integrity passed.")
