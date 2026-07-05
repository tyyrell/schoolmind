from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schoolmind.config import PLANS
from schoolmind.services.billing import annual_effective_monthly, annual_savings, pricing_catalog


def fail(message):
    raise AssertionError(message)


def main():
    standard = PLANS.get("starter")
    pro = PLANS.get("growth")
    custom = PLANS.get("scale")
    if not standard or standard["price"] != 50 or standard["student_limit"] != 300:
        fail("Standard plan must be $50/month with a 300-student included limit.")
    if not pro or pro["price"] != 120 or pro["student_limit"] != 1000:
        fail("Pro plan must be $120/month with a 1,000-student included limit.")
    if not custom or custom["price"] != 0:
        fail("Custom plan must not present a fake fixed monthly price.")
    if annual_savings("starter") <= 0 or annual_savings("growth") <= 0:
        fail("Annual billing must show a real saving against monthly billing.")
    if annual_effective_monthly("starter") >= standard["price"]:
        fail("Standard annual effective monthly price must be lower than monthly.")
    if annual_effective_monthly("growth") >= pro["price"]:
        fail("Pro annual effective monthly price must be lower than monthly.")
    catalog = pricing_catalog()
    if len(catalog) != 3:
        fail("Pricing catalog must expose exactly the three owner-approved plan lanes.")
    pricing = (ROOT / "schoolmind/templates/public/pricing.html").read_text(encoding="utf-8")
    required = [
        "30-day evaluation trial",
        "Start monthly trial",
        "Start annual trial",
        "Plan comparison",
        "No surprise conversion",
        "Extra seats",
        "This is not a fake-free funnel",
        "Manual activation stays locked",
    ]
    for needle in required:
        if needle not in pricing:
            fail(f"Pricing page missing required billing copy: {needle}")
    start = (ROOT / "schoolmind/templates/auth/start.html").read_text(encoding="utf-8")
    if "Preferred billing after trial" not in start or "billing_cycle" not in start:
        fail("Trial signup must capture intended post-trial billing cycle.")
    billing = (ROOT / "schoolmind/templates/dashboard/billing.html").read_text(encoding="utf-8")
    for needle in ["Open monthly checkout", "Open annual checkout", "Provider checkout required", "Manual activation is locked"]:
        if needle not in billing:
            fail(f"Dashboard billing page missing: {needle}")
    service = (ROOT / "schoolmind/services/billing.py").read_text(encoding="utf-8")
    for needle in ["CHECKOUT_{plan_key}_{cycle.upper()}_URL", "normalize_billing_cycle", "pricing_catalog"]:
        if needle not in service:
            fail(f"Billing service missing: {needle}")
    print("Billing audit passed: pricing, annual billing, checkout guardrails, and trial boundaries verified.")


if __name__ == "__main__":
    main()
