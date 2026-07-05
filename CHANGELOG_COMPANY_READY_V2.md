# SchoolMind AI Company Ready v2 Changelog

## Added
- Public company pages: Schools, Teachers, Counselors, Students, Pilot, FAQ, Accessibility, Data Retention, Subprocessors.
- SEO discovery routes: `/robots.txt` and `/sitemap.xml`.
- Language query switching via `?language=ar` and `?language=en`.
- Guided demo view counter and recurring signup reminders.
- Guided demo locked-action counter shown in the demo banner.
- Tests for new public pages, discovery files, Arabic RTL switching, and guided demo locks.

## Changed
- Expanded base navigation and footer to look like a serious company/product site.
- Billing page now hides the manual activation form unless `ALLOW_SCHOOL_ADMIN_MANUAL_BILLING=true`.
- Rate limiting and audit IP logging now use a `client_ip()` helper instead of blindly trusting `X-Forwarded-For`.
- `.env.example` now includes `TRUST_PROXY_HEADERS=false` with guidance.

## Verified
- `python3 run_tests.py`: 75 passed, 1 skipped.
- `python3 scripts/route_audit.py`: 99 endpoints checked.
- `python3 scripts/preflight.py`: passed with expected missing-production-provider warnings.
