#!/usr/bin/env python3
"""Audit Phase 15 performance and mobile safeguards."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "schoolmind" / "templates" / "base.html"
CSS = ROOT / "schoolmind" / "static" / "css" / "performance-mobile.css"
TEMPLATES = ROOT / "schoolmind" / "templates"


def fail(message: str) -> None:
    raise SystemExit(f"Performance/mobile audit failed: {message}")


def main() -> None:
    base = BASE.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""
    if "performance-mobile.css" not in base:
        fail("base.html does not load performance-mobile.css")
    if base.index("company.css") > base.index("performance-mobile.css"):
        fail("performance-mobile.css must load after company.css")

    required_css = [
        "content-visibility: auto",
        "contain-intrinsic-size",
        "100dvh",
        "env(safe-area-inset-bottom)",
        "prefers-reduced-motion",
        "prefers-reduced-data",
        "overflow-x: hidden",
        "min-height: var(--tap-target)",
        "@media (max-width: 640px)",
    ]
    for token in required_css:
        if token not in css:
            fail(f"missing CSS safeguard: {token}")

    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r"<img\b([^>]*)>", text):
            attrs = match.group(1)
            rel = template.relative_to(ROOT)
            if "width=" not in attrs or "height=" not in attrs:
                fail(f"image missing dimensions in {rel}")
            if 'decoding="async"' not in attrs:
                fail(f"image missing async decoding in {rel}")
            if 'fetchpriority="high"' not in attrs and 'loading="lazy"' not in attrs:
                fail(f"non-hero image missing lazy loading in {rel}")

    public_index = (TEMPLATES / "public" / "index.html").read_text(encoding="utf-8")
    if public_index.count('fetchpriority="high"') != 1:
        fail("homepage should have exactly one high-priority image")
    if public_index.count('loading="lazy"') < 4:
        fail("homepage should lazy-load below-the-fold images")

    print("Performance/mobile audit passed")


if __name__ == "__main__":
    main()
