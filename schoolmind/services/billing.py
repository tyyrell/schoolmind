from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from flask import current_app
from ..config import PLANS
from ..db import execute, query_one, utcnow
from .validators import valid_checkout_url


def plan_options():
    return PLANS


BILLING_CYCLES = {"monthly", "annual"}


def normalize_billing_cycle(value):
    cycle = (value or "monthly").strip().lower()
    return cycle if cycle in BILLING_CYCLES else "monthly"


def checkout_url_for(plan, billing_cycle="monthly"):
    cycle = normalize_billing_cycle(billing_cycle)
    plan_key = (plan or "").upper()
    cycle_key = f"CHECKOUT_{plan_key}_{cycle.upper()}_URL"
    fallback_key = f"CHECKOUT_{plan_key}_URL"
    url = current_app.config.get(cycle_key, "") or current_app.config.get(fallback_key, "")
    return url if valid_checkout_url(url) else ""


def plan_price(plan):
    return PLANS.get(plan, PLANS["starter"])["price"]


def plan_student_limit(plan):
    return PLANS.get(plan, PLANS["starter"])["student_limit"]


def plan_staff_limit(plan):
    return PLANS.get(plan, PLANS["starter"])["staff_limit"]


def annual_price(plan):
    return PLANS.get(plan, PLANS["starter"]).get("annual_price", 0)


def annual_savings(plan):
    data = PLANS.get(plan, PLANS["starter"])
    if not data.get("price") or not data.get("annual_price"):
        return 0
    return max(0, int(data["price"]) * 12 - int(data["annual_price"]))


def annual_effective_monthly(plan):
    data = PLANS.get(plan, PLANS["starter"])
    if not data.get("annual_price"):
        return 0
    return round(int(data["annual_price"]) / 12, 2)


def seats_for_plan(plan):
    return plan_student_limit(plan)


def extra_student_policy(plan):
    data = PLANS.get(plan, PLANS["starter"])
    return {
        "student_limit": data.get("student_limit", 0),
        "staff_limit": data.get("staff_limit", 0),
        "extra_student_fee": data.get("extra_student_fee", "Custom after limit"),
        "extra_student_note": data.get("extra_student_note", "Additional students can be priced separately after the included limit."),
    }


def pricing_catalog():
    catalog = []
    for key, plan in PLANS.items():
        monthly = int(plan.get("price") or 0)
        annual = int(plan.get("annual_price") or 0)
        catalog.append({
            "key": key,
            "name": plan["name"],
            "tagline": plan["tagline"],
            "monthly_price": monthly,
            "annual_price": annual,
            "annual_effective_monthly": annual_effective_monthly(key),
            "annual_savings": annual_savings(key),
            "student_limit": plan.get("student_limit", 0),
            "staff_limit": plan.get("staff_limit", 0),
            "limits": plan["limits"],
            "extra_student_fee": plan.get("extra_student_fee", "Custom"),
            "extra_student_note": plan.get("extra_student_note", ""),
            "features": plan.get("features", []),
            "best_for": plan.get("best_for", ""),
            "trial_note": plan.get("trial_note", "30-day trial for evaluation."),
            "is_custom": monthly == 0,
        })
    return catalog


def checkout_query(plan, billing_cycle="monthly"):
    cycle = normalize_billing_cycle(billing_cycle)
    return urlencode({"plan": plan, "billing_cycle": cycle})


def can_add_role(plan, role, current_count):
    if role == "student":
        return current_count < plan_student_limit(plan)
    return current_count < plan_staff_limit(plan)


def feature_limits(plan):
    base = {
        "starter": {"ai_daily": 30, "active_goals": 5, "games": True, "exports": "basic", "developer_controls": False},
        "growth": {"ai_daily": 200, "active_goals": 15, "games": True, "exports": "full", "developer_controls": False},
        "scale": {"ai_daily": 1000, "active_goals": 30, "games": True, "exports": "full", "developer_controls": True},
    }
    return base.get(plan, base["starter"])


def school_access_state(school):
    status = record_value(school, "status", "cancelled")
    if status == "active":
        return {"ok": True, "status": status, "message": ""}
    if status == "trial":
        trial_ends_at = record_value(school, "trial_ends_at")
        if not trial_ends_at:
            return {"ok": True, "status": status, "message": ""}
        try:
            ends_at = datetime.fromisoformat(str(trial_ends_at).replace("Z", "+00:00"))
        except ValueError:
            return {"ok": True, "status": status, "message": ""}
        if datetime.now(UTC) <= ends_at:
            return {"ok": True, "status": status, "message": ""}
        return {"ok": False, "status": "trial_expired", "message": "The trial has ended. Admin billing access remains available."}
    if status == "past_due":
        return {"ok": False, "status": status, "message": "Billing is past due. Admin billing access remains available."}
    return {"ok": False, "status": status, "message": "This workspace is not active."}


def record_value(record, key, default=None):
    if not record:
        return default
    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def coupon_is_valid(coupon, plan):
    if not coupon or coupon["status"] != "active":
        return False, "Coupon is not active."
    if coupon["applies_to_plan"] not in {"all", plan}:
        return False, "Coupon does not apply to this plan."
    if int(coupon["redeemed_count"] or 0) >= int(coupon["max_redemptions"] or 0):
        return False, "Coupon reached its redemption limit."
    if coupon["expires_at"] and coupon["expires_at"] < utcnow():
        return False, "Coupon expired."
    return True, ""


def preview_coupon(code, plan):
    clean_code = (code or "").strip().upper()
    amount = plan_price(plan)
    if not clean_code:
        return {"ok": True, "code": "", "base_amount": amount, "discount_percent": 0, "discount_amount": 0, "final_amount": amount, "message": ""}
    coupon = query_one("SELECT * FROM coupon_codes WHERE code = ?", (clean_code,))
    ok, message = coupon_is_valid(coupon, plan)
    if not ok:
        return {"ok": False, "code": clean_code, "base_amount": amount, "discount_percent": 0, "discount_amount": 0, "final_amount": amount, "message": message}
    discount_percent = int(coupon["discount_percent"])
    discount_amount = round(amount * discount_percent / 100)
    return {
        "ok": True,
        "coupon": coupon,
        "code": clean_code,
        "base_amount": amount,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "final_amount": max(0, amount - discount_amount),
        "message": f"{discount_percent}% discount applied.",
    }


def activate_subscription_with_coupon(school_id, plan, coupon_code="", provider_reference="manual"):
    preview = preview_coupon(coupon_code, plan)
    if not preview["ok"]:
        return False, preview["message"]
    cur = execute(
        """
        INSERT INTO subscriptions
        (school_id, plan, status, seats, monthly_price, discount_percent, coupon_code, checkout_reference, current_period_end, renewed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            school_id,
            plan,
            "active",
            seats_for_plan(plan),
            preview["final_amount"],
            preview["discount_percent"],
            preview["code"],
            provider_reference,
            (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            utcnow(),
            utcnow(),
        ),
    )
    execute("UPDATE schools SET plan = ?, status = 'active' WHERE id = ?", (plan, school_id))
    if preview["code"] and preview.get("coupon"):
        execute("UPDATE coupon_codes SET redeemed_count = redeemed_count + 1 WHERE id = ?", (preview["coupon"]["id"],))
        execute(
            "INSERT INTO coupon_redemptions (coupon_id, school_id, subscription_id, discount_amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (preview["coupon"]["id"], school_id, cur.lastrowid, preview["discount_amount"], utcnow()),
        )
    return True, "Subscription activated."
