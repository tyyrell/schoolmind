from datetime import UTC, datetime, timedelta
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash, current_app, session, g
from werkzeug.security import generate_password_hash
from .config import PLANS
from .db import ensure_platform_preferences, ensure_school_settings, ensure_user_preferences, execute, query_all, query_one, seed_demo_data, utcnow
from .i18n import FONT_SIZES, normalize_language, normalize_theme
from .security import rate_limit, require_csrf, safe_referrer_redirect
from .services.validators import clean_text, normalize_email, valid_email
from .services.billing import normalize_billing_cycle, pricing_catalog
from .services.mailer import queue_email, queue_template_email
from .services.ai_safety import AI_SAFETY_PRINCIPLES, AI_SAFETY_DO_LIST, AI_SAFETY_DO_NOT_LIST, PUBLIC_AI_SAFETY_STATEMENT
from .services.seo import PAGE_SEO, sitemap_entries
from .services.legal_trust import (
    DATA_RIGHTS_WORKFLOW,
    DPA_SECTIONS,
    INCIDENT_RESPONSE_STEPS,
    LEGAL_NOTICE,
    LEGAL_READINESS_MATRIX,
    PRIVACY_COMMITMENTS,
    STUDENT_NOTICE_POINTS,
)

bp = Blueprint("public", __name__)

DEMO_ROLE_ACCOUNTS = {
    "student": {"label": "Student", "name": "Sam Student", "email": "student@schoolmind.ai", "group_name": "Grade 10-A"},
    "teacher": {"label": "Teacher", "name": "Theo Teacher", "email": "teacher@schoolmind.ai", "group_name": "Grade 10-A"},
    "counselor": {"label": "Counselor", "name": "Cora Counselor", "email": "counselor@schoolmind.ai", "group_name": None},
    "admin": {"label": "Admin", "name": "Ava Admin", "email": "admin@schoolmind.ai", "group_name": None},
}


@bp.before_app_request
def apply_public_language_query():
    language = request.args.get("language")
    theme = request.args.get("theme")
    if language:
        session["language"] = normalize_language(language)
    if theme:
        session["theme"] = normalize_theme(theme)


@bp.route("/")
def index():
    return render_template("public/index.html", plans=PLANS, settings=public_site_settings())


@bp.route("/pricing")
def pricing():
    coupons = query_all("SELECT code, description, discount_percent, applies_to_plan FROM coupon_codes WHERE status = 'active' ORDER BY discount_percent DESC LIMIT 3")
    return render_template("public/pricing.html", plans=PLANS, pricing_catalog=pricing_catalog(), coupons=coupons)


@bp.route("/demo")
def demo():
    demo_accounts = [
        {"role": value["label"], "key": key, "email": value["email"], "password": "demo12345"}
        for key, value in DEMO_ROLE_ACCOUNTS.items()
    ]
    return render_template("public/demo.html", demo_accounts=demo_accounts)


@bp.route("/product")
def product():
    return render_template("public/product.html", plans=PLANS)


@bp.route("/features")
def features():
    return render_template("public/features.html")


@bp.route("/human-review")
def human_review():
    return render_template("public/human_review.html")


@bp.route("/compliance")
def compliance():
    return render_template("public/compliance.html")


@bp.route("/cookies")
def cookies():
    return render_template("public/cookies.html")


@bp.route("/request-demo")
def request_demo():
    return render_template("public/request_demo.html")


@bp.route("/contact-sales")
def contact_sales():
    return redirect(url_for("public.request_demo"))


@bp.route("/trial")
def trial():
    return render_template("public/trial.html", plans=PLANS)


@bp.route("/try")
@rate_limit("try_demo", max_requests=60, window_seconds=300)
def try_demo():
    user = ensure_demo_role_user("student")
    session.clear()
    session["user_id"] = user["id"]
    session["experience_mode"] = "guided_demo"
    session["experience_role"] = "student"
    session["personalization_dismissed"] = True
    flash("You are in a limited SchoolMind AI demo. Create a real workspace to save production data, invite staff, import students, or manage billing.", "success")
    return redirect(url_for("dashboard.app_home"))


@bp.route("/experience/<role>", methods=("POST",))
@rate_limit("instant_experience", max_requests=50, window_seconds=300)
@require_csrf
def instant_experience(role):
    role = (role or "").strip().lower()
    if role not in DEMO_ROLE_ACCOUNTS:
        flash("Choose a valid role to start the experience.", "error")
        return redirect(url_for("public.index"))
    user = ensure_demo_role_user(role)
    session.clear()
    session["user_id"] = user["id"]
    session["experience_mode"] = "guided_demo"
    session["experience_role"] = role
    session["personalization_dismissed"] = True
    flash(f"You are exploring SchoolMind AI as {DEMO_ROLE_ACCOUNTS[role]['label']} in limited demo mode. Create a workspace to save production data and unlock admin operations.", "success")
    return redirect(url_for("dashboard.app_home"))




@bp.route("/schools")
def schools():
    return render_template("public/schools.html")


@bp.route("/teachers")
def teachers():
    return render_template("public/teachers.html")


@bp.route("/counselors")
def counselors():
    return render_template("public/counselors.html")


@bp.route("/students")
def students():
    return render_template("public/students.html")


@bp.route("/pilot")
def pilot():
    return render_template("public/pilot.html")


@bp.route("/faq")
def faq():
    return render_template("public/faq.html")


@bp.route("/accessibility")
def accessibility():
    return render_template("public/accessibility.html")


@bp.route("/data-retention")
def data_retention():
    return render_template("public/data_retention.html")


@bp.route("/subprocessors")
def subprocessors():
    return render_template("public/subprocessors.html")


@bp.route("/robots.txt")
def robots_txt():
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /platform/",
        "Disallow: /app/",
        "Disallow: /api/",
        "Disallow: /login",
        "Disallow: /logout",
        "Disallow: /forgot-password",
        "Disallow: /reset-password",
        "Disallow: /accept-invite",
        "Disallow: /preferences",
        "Disallow: /start",
        f"Sitemap: {url_for('public.sitemap_xml', _external=True)}",
        f"Host: {current_app.config.get('PUBLIC_BASE_URL', request.url_root).rstrip('/')}",
        "",
    ])
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml():
    rows = []
    for entry in sitemap_entries():
        alternate_rows = "".join(
            f"    <xhtml:link rel=\"alternate\" hreflang=\"{lang}\" href=\"{href}\" />\n"
            for lang, href in entry["alternates"].items()
        )
        rows.append(
            "  <url>\n"
            f"    <loc>{entry['loc']}</loc>\n"
            f"    <lastmod>{entry['lastmod']}</lastmod>\n"
            f"    <changefreq>{entry['changefreq']}</changefreq>\n"
            f"    <priority>{entry['priority']}</priority>\n"
            f"{alternate_rows}"
            "  </url>\n"
        )
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\" "
        "xmlns:xhtml=\"http://www.w3.org/1999/xhtml\">\n"
        + "".join(rows)
        + "</urlset>\n"
    )
    return Response(xml, mimetype="application/xml")


@bp.route("/humans.txt")
def humans_txt():
    body = "\n".join([
        "SchoolMind AI",
        "Purpose: Privacy-aware school wellbeing and student support workflows.",
        "Language: English default, Arabic supported.",
        "Contact: " + current_app.config.get("SUPPORT_EMAIL", "support@schoolmind.ai"),
        "Security: /security",
        "AI safety: /ai-safety",
        "",
    ])
    return Response(body, mimetype="text/plain")


@bp.route("/llms.txt")
def llms_txt():
    body = "\n".join([
        "# SchoolMind AI",
        "",
        "SchoolMind AI is a bilingual EdTech SaaS platform for school wellbeing, student support workflows, and privacy-aware educational indicators.",
        "It is designed for human-supervised school review. It does not diagnose, treat, replace counselors, or provide emergency response.",
        "",
        "## Key public pages",
        "- /product: product overview",
        "- /features: feature catalog",
        "- /pricing: plans and 30-day trial",
        "- /demo: limited instant demo",
        "- /trial: trial versus pilot explanation",
        "- /security: security posture",
        "- /ai-safety: AI safety boundaries",
        "- /privacy: privacy overview",
        "- /data-processing-agreement: draft DPA structure",
        "- /student-data-notice: student-facing data notice",
        "",
    ])
    return Response(body, mimetype="text/plain")


@bp.route("/safety")
@bp.route("/ai-safety")
def safety():
    return render_template(
        "public/safety.html",
        principles=AI_SAFETY_PRINCIPLES,
        do_list=AI_SAFETY_DO_LIST,
        do_not_list=AI_SAFETY_DO_NOT_LIST,
        safety_statement=PUBLIC_AI_SAFETY_STATEMENT,
    )


@bp.route("/security")
def security():
    return render_template("public/security.html")


@bp.route("/about")
def about():
    return render_template("public/about.html")


@bp.route("/implementation")
def implementation():
    return render_template("public/implementation.html")


@bp.route("/preferences", methods=("POST",))
@require_csrf
def public_preferences():
    session["language"] = normalize_language(request.form.get("language"))
    session["theme"] = normalize_theme(request.form.get("theme"))
    return safe_referrer_redirect("public.index")


@bp.route("/preferences/personalize", methods=("POST",))
@require_csrf
def personalize_preferences():
    intent = request.form.get("intent", "save")
    if intent == "dismiss":
        session["personalization_dismissed"] = True
        save_personalization_state(completed=False, dismissed=True)
        return safe_referrer_redirect("public.index")

    language = normalize_language(request.form.get("language"))
    theme = normalize_theme(request.form.get("theme"))
    font_size = request.form.get("font_size") if request.form.get("font_size") in FONT_SIZES else "normal"
    reduced_motion = 1 if request.form.get("reduced_motion") == "on" else 0
    high_contrast = 1 if request.form.get("high_contrast") == "on" else 0
    dyslexia_friendly = 1 if request.form.get("dyslexia_friendly") == "on" else 0

    session["language"] = language
    session["theme"] = theme
    session["font_size"] = font_size
    session["reduced_motion"] = bool(reduced_motion)
    session["high_contrast"] = bool(high_contrast)
    session["dyslexia_friendly"] = bool(dyslexia_friendly)
    session["personalization_completed"] = True
    session.pop("personalization_dismissed", None)

    user = getattr(g, "user", None)
    platform_admin = getattr(g, "platform_admin", None)
    if user:
        ensure_user_preferences(user["id"])
        execute(
            """
            UPDATE user_preferences
            SET language = ?, theme = ?, font_size = ?, reduced_motion = ?, high_contrast = ?, dyslexia_friendly = ?,
                personalization_completed = 1, personalization_dismissed = 0, updated_at = ?
            WHERE user_id = ?
            """,
            (language, theme, font_size, reduced_motion, high_contrast, dyslexia_friendly, utcnow(), user["id"]),
        )
    elif platform_admin:
        ensure_platform_preferences(platform_admin["id"])
        execute(
            """
            UPDATE platform_admin_preferences
            SET language = ?, theme = ?, font_size = ?, reduced_motion = ?, high_contrast = ?, dyslexia_friendly = ?,
                personalization_completed = 1, personalization_dismissed = 0, updated_at = ?
            WHERE admin_id = ?
            """,
            (language, theme, font_size, reduced_motion, high_contrast, dyslexia_friendly, utcnow(), platform_admin["id"]),
        )
    flash("Experience preferences saved.", "success")
    return safe_referrer_redirect("public.index")


@bp.route("/privacy")
def privacy():
    return render_template(
        "public/privacy.html",
        legal_notice=LEGAL_NOTICE,
        commitments=PRIVACY_COMMITMENTS,
        data_rights_workflow=DATA_RIGHTS_WORKFLOW,
        readiness_matrix=LEGAL_READINESS_MATRIX,
    )


@bp.route("/dpa")
@bp.route("/data-processing-agreement")
def data_processing_agreement():
    return render_template("public/data_processing_agreement.html", legal_notice=LEGAL_NOTICE, dpa_sections=DPA_SECTIONS)


@bp.route("/student-data-notice")
def student_data_notice():
    return render_template("public/student_data_notice.html", legal_notice=LEGAL_NOTICE, notice_points=STUDENT_NOTICE_POINTS)


@bp.route("/incident-response")
def incident_response():
    return render_template("public/incident_response.html", legal_notice=LEGAL_NOTICE, incident_steps=INCIDENT_RESPONSE_STEPS)


@bp.route("/terms")
def terms():
    return render_template("public/terms.html", legal_notice=LEGAL_NOTICE)


@bp.route("/contact", methods=("GET", "POST"))
@rate_limit("contact", max_requests=20, window_seconds=600)
@require_csrf
def contact():
    if request.method == "POST":
        lead = normalize_sales_lead(request.form)
        if len(lead["name"]) < 2 or not valid_email(lead["email"]) or len(lead["message"]) < 8:
            flash("Name, valid email, and a useful message are required.", "error")
            return safe_referrer_redirect("public.contact")
        execute(
            """
            INSERT INTO sales_leads (
                name, email, school_name, message, status, lead_type, requested_plan, billing_cycle,
                student_count, launch_timeline, preferred_path, role_interest, privacy_review_needed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["name"],
                lead["email"],
                lead["school_name"],
                lead["message"],
                "new",
                lead["lead_type"],
                lead["requested_plan"],
                lead["billing_cycle"],
                lead["student_count"],
                lead["launch_timeline"],
                lead["preferred_path"],
                lead["role_interest"],
                lead["privacy_review_needed"],
                utcnow(),
            ),
        )
        queue_sales_lead_notification(lead)
        if lead["lead_type"] == "pilot":
            flash("Pilot request captured. A guided pilot should begin with scope, privacy review, staff workflow design, and launch criteria before real student data is used.", "success")
            return redirect(url_for("public.pilot"))
        if lead["lead_type"] == "demo":
            flash("Demo request captured. Use the limited demo instantly while the school walkthrough is arranged.", "success")
            return redirect(url_for("public.request_demo"))
        flash("Message captured for the school team. Connect an email provider before production launch so leads do not stay only in the database.", "success")
        return redirect(url_for("public.contact"))
    return render_template("public/contact.html", support_email=current_app.config["SUPPORT_EMAIL"])


def normalize_sales_lead(form):
    lead_type = clean_text(form.get("lead_type"), 24).lower() or "contact"
    if lead_type not in {"contact", "demo", "pilot", "trial"}:
        lead_type = "contact"
    requested_plan = clean_text(form.get("requested_plan"), 24).lower()
    if requested_plan not in {"starter", "growth", "scale", ""}:
        requested_plan = ""
    billing_cycle = normalize_billing_cycle(form.get("billing_cycle")) if form.get("billing_cycle") else ""
    preferred_path = clean_text(form.get("preferred_path"), 40).lower()
    if preferred_path not in {"self_serve_trial", "guided_pilot", "demo_first", "not_sure", ""}:
        preferred_path = "not_sure"
    raw_student_count = clean_text(form.get("student_count"), 20).replace(",", "")
    student_count = int(raw_student_count) if raw_student_count.isdigit() else 0
    return {
        "name": clean_text(form.get("name"), 120),
        "email": normalize_email(form.get("email")),
        "school_name": clean_text(form.get("school_name"), 160),
        "message": clean_text(form.get("message"), 2000),
        "lead_type": lead_type,
        "requested_plan": requested_plan,
        "billing_cycle": billing_cycle,
        "student_count": max(0, min(student_count, 500000)),
        "launch_timeline": clean_text(form.get("launch_timeline"), 80),
        "preferred_path": preferred_path,
        "role_interest": clean_text(form.get("role_interest"), 80),
        "privacy_review_needed": 1 if form.get("privacy_review_needed") == "on" else 0,
    }


def queue_sales_lead_notification(lead):
    support_email = current_app.config.get("SUPPORT_EMAIL", "support@schoolmind.ai")
    context = {
        "lead_type": lead["lead_type"].title(),
        "name": lead["name"],
        "email": lead["email"],
        "school_name": lead["school_name"] or "not specified",
        "school_name_or_name": lead["school_name"] or lead["name"],
        "requested_plan": lead["requested_plan"] or "not specified",
        "billing_cycle": lead["billing_cycle"] or "not specified",
        "student_count": lead["student_count"] or "not specified",
        "preferred_path": lead["preferred_path"] or "not specified",
        "launch_timeline": lead["launch_timeline"] or "not specified",
        "role_interest": lead["role_interest"] or "not specified",
        "privacy_review_needed": "yes" if lead["privacy_review_needed"] else "not specified",
        "message": lead["message"],
    }
    try:
        queue_template_email(None, support_email, "sales_lead_notification", context, message_type="sales_lead", metadata=lead["lead_type"])
    except Exception:
        current_app.logger.exception("sales_lead_notification_queue_failed")


def public_site_settings():
    try:
        return {row["key"]: row["value"] for row in query_all("SELECT key, value FROM site_settings")}
    except Exception:
        return {}


def save_personalization_state(completed=False, dismissed=False):
    user = getattr(g, "user", None)
    platform_admin = getattr(g, "platform_admin", None)
    if user:
        ensure_user_preferences(user["id"])
        execute(
            """
            UPDATE user_preferences
            SET personalization_completed = ?, personalization_dismissed = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (1 if completed else 0, 1 if dismissed else 0, utcnow(), user["id"]),
        )
    elif platform_admin:
        ensure_platform_preferences(platform_admin["id"])
        execute(
            """
            UPDATE platform_admin_preferences
            SET personalization_completed = ?, personalization_dismissed = ?, updated_at = ?
            WHERE admin_id = ?
            """,
            (1 if completed else 0, 1 if dismissed else 0, utcnow(), platform_admin["id"]),
        )


def ensure_demo_role_user(role):
    seed_demo_data()
    now = utcnow()
    trial_end = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    school = query_one("SELECT * FROM schools WHERE slug = ?", ("pixel-academy",))
    if not school:
        school_id = execute(
            "INSERT INTO schools (name, slug, country, plan, status, trial_ends_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("SchoolMind Demo School", "pixel-academy", "Global", "growth", "trial", trial_end, now),
        ).lastrowid
        school = query_one("SELECT * FROM schools WHERE id = ?", (school_id,))
    else:
        execute(
            "UPDATE schools SET name = 'SchoolMind Demo School', country = 'Global', status = 'trial', trial_ends_at = ?, plan = 'growth' WHERE id = ?",
            (trial_end, school["id"]),
        )
    ensure_school_settings(school["id"])
    if not query_one("SELECT id FROM subscriptions WHERE school_id = ?", (school["id"],)):
        execute(
            "INSERT INTO subscriptions (school_id, plan, status, seats, monthly_price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (school["id"], "growth", "trialing", 1500, PLANS["growth"]["price"], now),
        )
    account = DEMO_ROLE_ACCOUNTS[role]
    user = query_one("SELECT * FROM users WHERE email = ?", (account["email"],))
    if not user:
        execute(
            "INSERT INTO users (school_id, name, email, password_hash, role, group_name, password_changed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (school["id"], account["name"], account["email"], generate_password_hash("demo12345"), role, account["group_name"], now, now),
        )
    else:
        execute(
            "UPDATE users SET school_id = ?, role = ?, group_name = ?, is_active = 1, failed_login_count = 0, locked_until = NULL WHERE id = ?",
            (school["id"], role, account["group_name"], user["id"]),
        )
    user = query_one("SELECT * FROM users WHERE email = ?", (account["email"],))
    if role == "student" and not query_one("SELECT id FROM consent_records WHERE school_id = ? AND student_id = ? AND status = 'recorded'", (school["id"], user["id"])):
        admin = query_one("SELECT id FROM users WHERE school_id = ? AND role = 'admin' ORDER BY id LIMIT 1", (school["id"],))
        execute(
            "INSERT INTO consent_records (school_id, student_id, guardian_name, guardian_email, status, note, recorded_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (school["id"], user["id"], "Demo Guardian", "guardian@example.com", "recorded", "Demo consent record only.", admin["id"] if admin else user["id"], now),
        )
    return user
