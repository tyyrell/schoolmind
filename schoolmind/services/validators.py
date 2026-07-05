import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_email(value):
    return (value or "").strip().lower()


def valid_email(value):
    return bool(EMAIL_RE.match(normalize_email(value)))


def slugify(value, fallback="school"):
    text = SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return text or fallback


def clean_text(value, limit=1000):
    text = (value or "").replace(chr(0), "").strip()
    return text[:limit]


def valid_checkout_url(value):
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
