from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse, urlunparse

from flask import current_app, request

SUPPORTED_SEO_LANGUAGES = ("en", "ar")

DEFAULT_DESCRIPTION = (
    "SchoolMind AI is a bilingual school wellbeing and student support platform "
    "for privacy-aware educational indicators, guided workflows, and human-supervised school insights."
)

PAGE_SEO = {
    "public.index": {
        "path": "/",
        "title": "SchoolMind AI · Human-supervised school wellbeing platform",
        "title_ar": "SchoolMind AI · منصة دعم ورفاه مدرسي بإشراف بشري",
        "description": "Explore SchoolMind AI instantly, start a 30-day school trial, or request a guided pilot for privacy-aware student support workflows.",
        "description_ar": "جرّب SchoolMind AI فورًا، أو ابدأ تجربة مدرسية لمدة 30 يومًا، أو اطلب تجربة موجهة لسير عمل دعم الطلاب مع مراعاة الخصوصية.",
        "keywords": "school wellbeing platform, student support software, EdTech SaaS, school counselor workflow, bilingual school platform",
        "priority": "1.0",
        "changefreq": "weekly",
    },
    "public.product": {
        "path": "/product",
        "title": "Product overview · SchoolMind AI",
        "description": "A role-based school support platform for students, teachers, counselors, and school leaders with human-reviewed educational indicators.",
        "keywords": "school support platform, role based dashboards, educational indicators",
        "priority": "0.9",
        "changefreq": "monthly",
    },
    "public.features": {
        "path": "/features",
        "title": "Features · SchoolMind AI",
        "description": "Explore SchoolMind AI features for instant demo access, bilingual support, teacher insights, counselor workflows, and admin operations.",
        "keywords": "SchoolMind AI features, teacher insights, counselor workflow, school admin dashboard",
        "priority": "0.9",
        "changefreq": "monthly",
    },
    "public.pricing": {
        "path": "/pricing",
        "title": "Pricing · SchoolMind AI",
        "description": "SchoolMind AI pricing starts with a 30-day trial, $50/month Standard, $120/month Pro, annual discounts, and guided custom pilots.",
        "keywords": "SchoolMind AI pricing, school SaaS pricing, 30 day school trial",
        "priority": "0.9",
        "changefreq": "monthly",
    },
    "public.trial": {
        "path": "/trial",
        "title": "30-day trial · SchoolMind AI",
        "description": "Compare instant demo access, a 30-day self-serve school trial, and a guided pilot for larger school deployments.",
        "keywords": "SchoolMind AI trial, guided pilot, school software trial",
        "priority": "0.8",
        "changefreq": "monthly",
    },
    "public.demo": {
        "path": "/demo",
        "title": "Instant demo · SchoolMind AI",
        "description": "Try SchoolMind AI immediately in a limited sandbox before creating a real school workspace.",
        "keywords": "SchoolMind AI demo, try school platform, demo school dashboard",
        "priority": "0.8",
        "changefreq": "monthly",
    },
    "public.request_demo": {
        "path": "/request-demo",
        "title": "Request a demo · SchoolMind AI",
        "description": "Request a guided SchoolMind AI demo, trial consultation, or pilot scope review for your school.",
        "keywords": "request school demo, SchoolMind AI sales, guided school pilot",
        "priority": "0.8",
        "changefreq": "monthly",
    },
    "public.schools": {
        "path": "/schools",
        "title": "For schools · SchoolMind AI",
        "description": "See how SchoolMind AI helps school leaders coordinate student support, privacy governance, and wellbeing workflows.",
        "keywords": "school leaders, school wellbeing governance, student support operations",
        "priority": "0.8",
        "changefreq": "monthly",
    },
    "public.teachers": {
        "path": "/teachers",
        "title": "For teachers · SchoolMind AI",
        "description": "Aggregate classroom patterns and teacher-safe insights without exposing private journal content or counselor-only details.",
        "keywords": "teacher insights, classroom wellbeing patterns, aggregate school data",
        "priority": "0.75",
        "changefreq": "monthly",
    },
    "public.counselors": {
        "path": "/counselors",
        "title": "For counselors · SchoolMind AI",
        "description": "Organize support queues, follow-ups, playbooks, and human-reviewed student support workflows for school counselors.",
        "keywords": "school counselor workflow, student support queue, counselor dashboard",
        "priority": "0.75",
        "changefreq": "monthly",
    },
    "public.students": {
        "path": "/students",
        "title": "For students · SchoolMind AI",
        "description": "A student-facing experience for check-ins, resources, progress, and supervised support boundaries.",
        "keywords": "student wellbeing check in, school support resources, student progress dashboard",
        "priority": "0.75",
        "changefreq": "monthly",
    },
    "public.implementation": {
        "path": "/implementation",
        "title": "Implementation · SchoolMind AI",
        "description": "Plan a responsible SchoolMind AI rollout with onboarding, governance, privacy review, staff setup, and launch readiness.",
        "keywords": "school software implementation, EdTech onboarding, school privacy governance",
        "priority": "0.75",
        "changefreq": "monthly",
    },
    "public.pilot": {
        "path": "/pilot",
        "title": "Guided pilot · SchoolMind AI",
        "description": "Run a guided SchoolMind AI pilot with scope, governance, privacy review, evaluation goals, and school launch support.",
        "keywords": "guided school pilot, EdTech pilot program, school software evaluation",
        "priority": "0.75",
        "changefreq": "monthly",
    },
    "public.security": {
        "path": "/security",
        "title": "Security · SchoolMind AI",
        "description": "Review SchoolMind AI security posture, role-based access, tenant boundaries, audit logs, and production hardening expectations.",
        "keywords": "SchoolMind AI security, school data security, EdTech security",
        "priority": "0.7",
        "changefreq": "monthly",
    },
    "public.safety": {
        "path": "/safety",
        "aliases": ("/ai-safety",),
        "title": "AI safety · SchoolMind AI",
        "description": "SchoolMind AI uses AI-assisted educational indicators with human review, not diagnosis, treatment, or emergency response.",
        "keywords": "AI safety school platform, human supervised AI, educational indicators",
        "priority": "0.7",
        "changefreq": "monthly",
    },
    "public.human_review": {
        "path": "/human-review",
        "title": "Human review · SchoolMind AI",
        "description": "SchoolMind AI is designed around human-supervised review workflows so schools retain responsibility for interpretation and action.",
        "keywords": "human review AI, school support review, supervised AI workflow",
        "priority": "0.65",
        "changefreq": "monthly",
    },
    "public.compliance": {
        "path": "/compliance",
        "title": "Compliance overview · SchoolMind AI",
        "description": "Understand SchoolMind AI readiness boundaries for school governance, privacy review, data processing, and production deployment.",
        "keywords": "school compliance overview, EdTech privacy readiness, school governance",
        "priority": "0.65",
        "changefreq": "monthly",
    },
    "public.privacy": {
        "path": "/privacy",
        "title": "Privacy · SchoolMind AI",
        "description": "Read the SchoolMind AI privacy overview for student data minimization, school control, role boundaries, and data rights workflows.",
        "keywords": "SchoolMind AI privacy, student data privacy, school privacy policy",
        "priority": "0.7",
        "changefreq": "monthly",
    },
    "public.terms": {
        "path": "/terms",
        "title": "Terms · SchoolMind AI",
        "description": "Review SchoolMind AI terms covering educational use, trial use, billing, acceptable use, and emergency boundaries.",
        "keywords": "SchoolMind AI terms, EdTech terms, school SaaS agreement",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.data_processing_agreement": {
        "path": "/data-processing-agreement",
        "aliases": ("/dpa",),
        "title": "Data Processing Agreement draft · SchoolMind AI",
        "description": "Review a draft DPA structure for SchoolMind AI school deployments, subprocessors, retention, confidentiality, and incident handling.",
        "keywords": "SchoolMind AI DPA, data processing agreement, school data processing",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.student_data_notice": {
        "path": "/student-data-notice",
        "title": "Student data notice · SchoolMind AI",
        "description": "A plain-language notice for how SchoolMind AI should communicate student data handling, visibility, and school oversight.",
        "keywords": "student data notice, school data transparency, student privacy",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.incident_response": {
        "path": "/incident-response",
        "title": "Incident response · SchoolMind AI",
        "description": "Review SchoolMind AI incident response expectations, triage, containment, investigation, notification, and remediation workflow.",
        "keywords": "incident response, school data incident, EdTech security incident",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.data_retention": {
        "path": "/data-retention",
        "title": "Data retention · SchoolMind AI",
        "description": "Understand SchoolMind AI data retention expectations for school-controlled workspaces and production governance.",
        "keywords": "school data retention, EdTech data retention, student data deletion",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.subprocessors": {
        "path": "/subprocessors",
        "title": "Subprocessors · SchoolMind AI",
        "description": "Review the SchoolMind AI subprocessor transparency page and production provider disclosure expectations.",
        "keywords": "SchoolMind AI subprocessors, EdTech vendors, school data providers",
        "priority": "0.55",
        "changefreq": "yearly",
    },
    "public.cookies": {
        "path": "/cookies",
        "title": "Cookie policy · SchoolMind AI",
        "description": "SchoolMind AI uses conservative cookies for security, preferences, and platform operation rather than default ad tracking.",
        "keywords": "SchoolMind AI cookies, school platform cookie policy, privacy friendly cookies",
        "priority": "0.45",
        "changefreq": "yearly",
    },
    "public.accessibility": {
        "path": "/accessibility",
        "title": "Accessibility · SchoolMind AI",
        "description": "Review SchoolMind AI accessibility support including language preferences, reduced motion, high contrast, and responsive layouts.",
        "keywords": "SchoolMind AI accessibility, accessible EdTech, RTL school platform",
        "priority": "0.55",
        "changefreq": "monthly",
    },
    "public.about": {
        "path": "/about",
        "title": "About · SchoolMind AI",
        "description": "Learn why SchoolMind AI is built for responsible, school-supervised support workflows and privacy-aware educational insights.",
        "keywords": "about SchoolMind AI, EdTech company, school wellbeing platform",
        "priority": "0.6",
        "changefreq": "monthly",
    },
    "public.faq": {
        "path": "/faq",
        "title": "FAQ · SchoolMind AI",
        "description": "Answers to common questions about SchoolMind AI trials, pilots, data, AI boundaries, language support, and school deployment.",
        "keywords": "SchoolMind AI FAQ, school platform questions, EdTech trial questions",
        "priority": "0.6",
        "changefreq": "monthly",
    },
    "public.contact": {
        "path": "/contact",
        "title": "Contact · SchoolMind AI",
        "description": "Contact SchoolMind AI about school trials, guided pilots, privacy review, implementation, and product questions.",
        "keywords": "contact SchoolMind AI, school software support, EdTech contact",
        "priority": "0.6",
        "changefreq": "monthly",
    },
}

PUBLIC_INDEX_ENDPOINTS = tuple(PAGE_SEO.keys())
NOINDEX_ENDPOINT_PREFIXES = ("auth.", "dashboard.", "platform.", "api.")


def public_base_url() -> str:
    configured = str(current_app.config.get("PUBLIC_BASE_URL", "") or "").strip()
    if configured:
        return configured.rstrip("/")
    return request.url_root.rstrip("/")


def absolute_public_url(path: str, language: str | None = None) -> str:
    path = path or "/"
    if not path.startswith("/"):
        path = "/" + path
    url = public_base_url() + path
    if language and language != "x-default":
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'language': language})}"
    return url


def normalize_canonical_url(url: str) -> str:
    parsed = urlparse(url)
    # Canonical URLs should not preserve marketing tags or temporary query state.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))


def current_language_code() -> str:
    try:
        from .i18n import normalize_language
        return normalize_language(getattr(request, "args", {}).get("language") or "") if request.args.get("language") else "en"
    except Exception:
        return "en"


def page_record_for_endpoint(endpoint: str | None) -> dict:
    return PAGE_SEO.get(endpoint or "", {})


def seo_meta_for_request(language: str = "en") -> dict:
    endpoint = request.endpoint or ""
    record = page_record_for_endpoint(endpoint)
    path = record.get("path") or request.path or "/"
    language = language if language in SUPPORTED_SEO_LANGUAGES else "en"
    title = record.get(f"title_{language}") or record.get("title") or "SchoolMind AI"
    description = record.get(f"description_{language}") or record.get("description") or DEFAULT_DESCRIPTION
    canonical = absolute_public_url(path, language if language != "en" else None)
    canonical = normalize_canonical_url(canonical) if language == "en" else canonical
    noindex = endpoint.startswith(NOINDEX_ENDPOINT_PREFIXES) or (endpoint and endpoint not in PAGE_SEO and endpoint.startswith("public.") is False)
    robots = "noindex, nofollow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"
    image = absolute_public_url("/static/img/og/schoolmind-og.png")
    alternates = {
        "en": absolute_public_url(path, None),
        "ar": absolute_public_url(path, "ar"),
        "x-default": absolute_public_url(path, None),
    }
    return {
        "title": title,
        "description": description,
        "keywords": record.get("keywords", "SchoolMind AI, school wellbeing, EdTech SaaS"),
        "canonical": canonical,
        "robots": robots,
        "og_title": title,
        "og_description": description,
        "og_type": "website",
        "og_url": canonical,
        "og_image": image,
        "twitter_title": title,
        "twitter_description": description,
        "twitter_image": image,
        "locale": "ar_AR" if language == "ar" else "en_US",
        "alternate_locale": "en_US" if language == "ar" else "ar_AR",
        "alternates": alternates,
        "structured_data": structured_data_for_page(endpoint, title, description, canonical, image),
    }


def organization_schema() -> dict:
    base = public_base_url()
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "SchoolMind AI",
        "url": base,
        "logo": absolute_public_url("/static/img/brand/schoolmind-logo.png"),
        "email": current_app.config.get("SUPPORT_EMAIL", "support@schoolmind.ai"),
        "sameAs": [],
    }


def software_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "SchoolMind AI",
        "applicationCategory": "EducationalApplication",
        "operatingSystem": "Web",
        "description": DEFAULT_DESCRIPTION,
        "offers": [
            {"@type": "Offer", "name": "Standard", "price": "50", "priceCurrency": "USD", "availability": "https://schema.org/OnlineOnly"},
            {"@type": "Offer", "name": "Pro", "price": "120", "priceCurrency": "USD", "availability": "https://schema.org/OnlineOnly"},
        ],
    }


def website_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "SchoolMind AI",
        "url": public_base_url(),
        "inLanguage": ["en", "ar"],
        "potentialAction": {
            "@type": "SearchAction",
            "target": absolute_public_url("/faq") + "?q={search_term_string}",
            "query-input": "required name=search_term_string",
        },
    }


def faq_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Can schools try SchoolMind AI before creating a workspace?",
                "acceptedAnswer": {"@type": "Answer", "text": "Yes. Visitors can explore a limited demo, while saving production data and managing billing requires a real workspace."},
            },
            {
                "@type": "Question",
                "name": "Does SchoolMind AI diagnose students?",
                "acceptedAnswer": {"@type": "Answer", "text": "No. SchoolMind AI provides educational support indicators for human review and does not diagnose, treat, or replace school professionals."},
            },
        ],
    }


def breadcrumb_schema(endpoint: str | None, title: str, canonical: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": public_base_url()},
            {"@type": "ListItem", "position": 2, "name": title.replace(" · SchoolMind AI", ""), "item": canonical},
        ],
    }


def structured_data_for_page(endpoint: str | None, title: str, description: str, canonical: str, image: str) -> list[dict]:
    data = [organization_schema(), website_schema()]
    if endpoint == "public.index":
        data.append(software_schema())
    if endpoint == "public.faq":
        data.append(faq_schema())
    if endpoint in PAGE_SEO and endpoint != "public.index":
        data.append(breadcrumb_schema(endpoint, title, canonical))
    data.append({
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": description,
        "url": canonical,
        "image": image,
        "isPartOf": {"@type": "WebSite", "name": "SchoolMind AI", "url": public_base_url()},
    })
    return data


def sitemap_entries() -> list[dict]:
    today = datetime.now(UTC).date().isoformat()
    entries = []
    for endpoint in PUBLIC_INDEX_ENDPOINTS:
        record = PAGE_SEO[endpoint]
        path = record["path"]
        entries.append({
            "endpoint": endpoint,
            "loc": absolute_public_url(path),
            "alternates": {
                "en": absolute_public_url(path),
                "ar": absolute_public_url(path, "ar"),
                "x-default": absolute_public_url(path),
            },
            "lastmod": today,
            "changefreq": record.get("changefreq", "monthly"),
            "priority": record.get("priority", "0.5"),
        })
    return entries
