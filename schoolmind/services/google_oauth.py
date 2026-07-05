import json
import os
import urllib.parse
import urllib.request


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(RuntimeError):
    pass


def google_config(default_redirect_uri=""):
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI", "").strip() or default_redirect_uri,
        "default_role": os.environ.get("GOOGLE_DEFAULT_ROLE", "student").strip().lower(),
        "default_school_slug": os.environ.get("GOOGLE_DEFAULT_SCHOOL_SLUG", "pixel-academy").strip().lower(),
        "allow_auto_create": os.environ.get("GOOGLE_ALLOW_AUTO_CREATE", "false").strip().lower() in {"1", "true", "yes", "on"},
    }


def is_google_enabled(default_redirect_uri=""):
    cfg = google_config(default_redirect_uri)
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])


def authorization_url(state, default_redirect_uri=""):
    cfg = google_config(default_redirect_uri)
    if not is_google_enabled(default_redirect_uri):
        raise GoogleOAuthError("Google OAuth is not configured.")
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code, default_redirect_uri=""):
    cfg = google_config(default_redirect_uri)
    payload = urllib.parse.urlencode(
        {
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": cfg["redirect_uri"],
        }
    ).encode("utf-8")
    request = urllib.request.Request(TOKEN_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            token = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise GoogleOAuthError("Google token exchange failed.") from exc
    access_token = token.get("access_token")
    if not access_token:
        raise GoogleOAuthError("Google did not return an access token.")
    return access_token


def fetch_profile(access_token):
    request = urllib.request.Request(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise GoogleOAuthError("Google profile fetch failed.") from exc
    return {
        "sub": str(profile.get("sub", "")).strip(),
        "email": str(profile.get("email", "")).strip().lower(),
        "name": str(profile.get("name") or profile.get("email") or "Google User").strip(),
        "avatar_url": str(profile.get("picture", "")).strip(),
        "email_verified": bool(profile.get("email_verified", False)),
    }


def complete_google_login(code, default_redirect_uri=""):
    access_token = exchange_code(code, default_redirect_uri)
    profile = fetch_profile(access_token)
    if not profile["sub"] or not profile["email"] or not profile["email_verified"]:
        raise GoogleOAuthError("Google account must have a verified email.")
    return profile
