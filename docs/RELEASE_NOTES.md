# SchoolMind AI — Company Ready Final Release Notes

## Release status

This release is a company-facing, bilingual EdTech SaaS build for strong demos, controlled pilots, and production setup. It is not a medical, emergency, therapy, or diagnosis product. It provides educational wellbeing indicators and school workflow support under human review.

## Major upgrades

- Company-grade SchoolMind AI public site with product, role, trust, legal, pricing, demo, trial, pilot, and contact pages.
- Instant limited demo flow inspired by modern SaaS products: visitors can explore immediately, while sensitive actions require signup.
- English default with Arabic RTL support and language switching.
- Visual asset system with optimized WebP fallbacks, image dimensions, lazy loading, and social preview imagery.
- Pricing UX for Standard `$50/month`, Pro `$120/month`, Custom, monthly/annual billing, 30-day trial, student limits, and checkout guardrails.
- Guided pilot path for serious schools that need governance, privacy review, and onboarding support.
- School launch onboarding with readiness score, blockers, launch profile, owner mapping, privacy/governance steps, and launch-ready controls.
- Role-based command centers for student, teacher, counselor, and school admin users.
- AI safety system with safe claim guardrails, human-review boundaries, and notices in high-risk product surfaces.
- Expanded legal/trust layer: Privacy, Terms, DPA, Student Data Notice, Incident Response, Data Retention, Subprocessors, Accessibility, Compliance, Human Review, and Cookie Policy.
- Security hardening: CSP without unsafe-inline/unsafe-eval, CSP nonce for JSON-LD, safe referrer redirects, stronger browser headers, no-store sensitive routes, release hygiene, and trusted proxy configuration.
- Email readiness: template-based invite/reset/lead/trial/test emails, outbox health, status counts, failed-attempt tracking, and test email flow.
- PostgreSQL/Supabase readiness: URL hardening, TLS requirements, connect/statement timeouts, application name, production database dashboard, and preflight checks.
- Performance/mobile polish: safe-area support, overflow safeguards, touch targets, responsive tables, content visibility, reduced motion/data handling, and image budget audit.
- SEO/discovery layer: page-specific metadata, canonical links, hreflang, Open Graph, Twitter cards, rich sitemap, robots.txt, humans.txt, llms.txt, and structured data.

## Verified QA

```text
Dedicated phase audits: passed
Route audit: 112 endpoints checked
Tests: 111 total, 110 passed, 1 skipped, 0 assertion failures
Release check: passed
```

The skipped test is optional and requires a live `TEST_DATABASE_URL` for PostgreSQL integration.

## Known production blockers

The code package is not enough by itself for a real commercial school launch. The owner must provide and verify:

- production PostgreSQL/Supabase database
- strong production secret key
- transactional email provider and DNS records
- payment checkout URLs and webhook secret
- final domain and public base URL
- real subprocessor list
- legal review for student data and school agreements
- backup/restore drill
- Redis rate limiting for scaled production
- admin/platform MFA before serious production usage

## Phase 17 Hotfix 1 — Render PostgreSQL migration order

- Fixed startup failure on existing PostgreSQL databases where `sales_leads.lead_type` did not exist yet.
- Database initialization now creates tables first, runs column migrations second, then creates indexes third.
- Added regression tests to ensure indexes that depend on migrated columns do not run before migrations.
- No database reset is required.

