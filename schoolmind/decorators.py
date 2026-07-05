from functools import wraps
from flask import g, redirect, url_for, session, abort, request
from .db import ensure_platform_preferences, ensure_user_preferences, query_one
from .services.billing import school_access_state


def load_logged_in_user():
    g.platform_admin = None
    g.preferences = None
    g.platform_preferences = None
    platform_admin_id = session.get("platform_admin_id")
    if platform_admin_id:
        g.platform_admin = query_one(
            "SELECT * FROM platform_admins WHERE id = ? AND is_active = 1",
            (platform_admin_id,),
        )
        g.platform_preferences = ensure_platform_preferences(g.platform_admin["id"]) if g.platform_admin else None
    user_id = session.get("user_id")
    if not user_id:
        g.user = None
        return
    g.user = query_one(
        """
        SELECT users.*, schools.name AS school_name, schools.plan AS school_plan, schools.status AS school_status, schools.trial_ends_at AS school_trial_ends_at
        FROM users
        JOIN schools ON schools.id = users.school_id
        WHERE users.id = ? AND users.is_active = 1
        """,
        (user_id,),
    )
    g.preferences = ensure_user_preferences(g.user["id"]) if g.user else None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            # Preserve the original requested path so the login page can
            # redirect back after successful authentication.
            next_path = request.path
            if request.query_string:
                try:
                    qs = request.query_string.decode("utf-8")
                except Exception:
                    qs = None
                if qs:
                    next_path = f"{next_path}?{qs}"
            return redirect(url_for("auth.login", next=next_path))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                next_path = request.path
                if request.query_string:
                    try:
                        qs = request.query_string.decode("utf-8")
                    except Exception:
                        qs = None
                    if qs:
                        next_path = f"{next_path}?{qs}"
                return redirect(url_for("auth.login", next=next_path))
            if g.user["role"] not in roles:
                abort(403)
            if g.user["school_status"] in {"suspended", "cancelled"}:
                abort(403)
            state = school_access_state({"status": g.user["school_status"], "trial_ends_at": g.user["school_trial_ends_at"]})
            billing_escape = request.endpoint in {
                "dashboard.admin_billing",
                "dashboard.billing_checkout",
                "dashboard.billing_manual_activate",
                "dashboard.admin_settings",
                "dashboard.admin_operations",
                "auth.logout",
            }
            if not state["ok"] and not (g.user["role"] == "admin" and billing_escape):
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def same_school_user(user_id):
    if g.user is None:
        return None
    return query_one("SELECT * FROM users WHERE id = ? AND school_id = ?", (user_id, g.user["school_id"]))



def platform_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if getattr(g, "platform_admin", None) is None:
            return redirect(url_for("platform.platform_login"))
        return view(*args, **kwargs)
    return wrapper
