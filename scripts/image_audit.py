#!/usr/bin/env python3
"""Audit public image usage for missing assets, fallbacks, and accessible metadata."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "schoolmind" / "templates"
STATIC = ROOT / "schoolmind" / "static"

IMAGE_RE = re.compile(r"filename='(?P<path>img/[^']+\.(?:png|jpg|jpeg|webp|svg))'")
IMG_TAG_RE = re.compile(r"<img\s+[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"(?P<name>[a-zA-Z:-]+)=\"(?P<value>[^\"]*)\"")


def fail(message: str) -> None:
    print(f"IMAGE AUDIT FAILED: {message}")
    sys.exit(1)


def attrs(tag: str) -> dict[str, str]:
    return {m.group("name").lower(): m.group("value") for m in ATTR_RE.finditer(tag)}


def main() -> int:
    missing: list[str] = []
    weak_tags: list[str] = []
    png_without_webp: list[str] = []

    for template in sorted(TEMPLATES.rglob("*.html")):
        text = template.read_text(encoding="utf-8")
        for match in IMAGE_RE.finditer(text):
            rel = match.group("path")
            if not (STATIC / rel).exists():
                missing.append(f"{template.relative_to(ROOT)} -> {rel}")
            if rel.startswith("img/pages/") and rel.endswith(".png"):
                webp = rel[:-4] + ".webp"
                if not (STATIC / webp).exists():
                    png_without_webp.append(f"{template.relative_to(ROOT)} -> {webp}")
        for match in IMG_TAG_RE.finditer(text):
            tag = match.group(0)
            values = attrs(tag)
            if not values.get("alt"):
                weak_tags.append(f"{template.relative_to(ROOT)} missing alt: {tag[:120]}")
            if "loading" not in values:
                weak_tags.append(f"{template.relative_to(ROOT)} missing loading: {tag[:120]}")
            if "width" not in values or "height" not in values:
                weak_tags.append(f"{template.relative_to(ROOT)} missing dimensions: {tag[:120]}")

    if missing:
        fail("Missing image files:\n" + "\n".join(missing))
    if png_without_webp:
        fail("PNG page assets without WebP fallback:\n" + "\n".join(png_without_webp))
    if weak_tags:
        fail("Weak image tags:\n" + "\n".join(weak_tags))

    print("Image audit passed: all referenced images exist, page PNGs have WebP fallbacks, and img tags include alt/loading/dimensions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
