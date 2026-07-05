# Company-Ready Change Log

## Added
- Company-facing SchoolMind AI public website structure.
- Integrated generated SchoolMind AI image assets.
- `/try` instant limited demo entry.
- `/security`, `/about`, and `/implementation` public pages.
- `company.css` polish layer.
- Favicon SVG and updated web app manifest.
- Open Graph/Twitter preview metadata.
- Demo mode guard for sensitive dashboard actions.
- `ALLOW_SCHOOL_ADMIN_MANUAL_BILLING` production safety flag.

## Changed
- Public branding now uses SchoolMind AI instead of the old Pixel SaaS wording.
- Plans now display Standard, Pro, and Custom with the approved pricing model.
- Trial form now presents a clearer 30-day trial with safe data wording.
- Demo pages now explain limits and signup prompts honestly.
- Inline dashboard progress styles were replaced with CSP-safe progress elements.

## Verified
- Full test suite passed: 72 passed, 1 skipped.
- Route audit passed: 88 endpoints checked.
- Production preflight passed with expected missing-provider warnings.
