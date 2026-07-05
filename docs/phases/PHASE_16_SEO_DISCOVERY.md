# Phase 16 — SEO and Discovery Polish

## Completed

- Added a centralized SEO service: `schoolmind/services/seo.py`.
- Replaced generic metadata in `base.html` with endpoint-aware metadata.
- Added canonical URLs, English/Arabic hreflang alternates, x-default alternates, page-specific descriptions, keywords, Open Graph, Twitter Card metadata, and robots directives.
- Added nonce-protected JSON-LD structured data for Organization, WebSite, SoftwareApplication, WebPage, BreadcrumbList, and FAQ where appropriate.
- Updated CSP to support nonce-based structured data without enabling unsafe inline scripts.
- Upgraded `/sitemap.xml` with `lastmod`, `changefreq`, `priority`, and xhtml alternate language links.
- Hardened `/robots.txt` with public allow rules and explicit disallows for app, admin, auth, and API routes.
- Added `/humans.txt` and `/llms.txt` for company and AI/discovery context.
- Added regression audit coverage via `scripts/seo_discovery_audit.py`.

## Still required before production

- Set `PUBLIC_BASE_URL` to the final domain.
- Replace default social image if a final brand-approved Open Graph image is chosen.
- Add live analytics only after cookie/privacy review.
- Validate previews in WhatsApp, LinkedIn, X, Facebook, and Google Rich Results.
