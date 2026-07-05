# Phase 11 — Privacy, Legal Trust, and Student Data Governance

## Goal

Move SchoolMind AI from short legal placeholder pages to a stronger school-readiness trust layer. The goal is not to fake legal compliance. The goal is to show schools exactly what is built, what needs approval, and what must be configured before real student data is used.

## Implemented

- Added a central legal/trust content module: `schoolmind/services/legal_trust.py`.
- Expanded `/privacy` into a structured privacy governance page.
- Expanded `/terms` with clearer boundaries for educational-only use, trial use, acceptable use, billing, and emergency limits.
- Added `/data-processing-agreement` and `/dpa` as a DPA draft outline.
- Added `/student-data-notice` for plain-language student/guardian communication.
- Added `/incident-response` for public incident response readiness.
- Added the new legal pages to the sitemap and footer.
- Added legal trust CSS for policy grids, readiness tables, and response steps.
- Added `scripts/legal_trust_audit.py` to prevent the legal trust system from being removed accidentally.

## Boundaries

These pages are strong product-readiness drafts. They are not a substitute for qualified legal review in the countries and school systems SchoolMind AI serves.

## Remaining production requirements

- Final company legal entity details.
- Final school agreement and DPA terms.
- Named subprocessors and regions.
- Named privacy/security contact.
- Data retention window and backup deletion policy.
- Payment provider terms and tax/invoicing approach.
- Legal review for target markets and student age groups.
