# Owner Production Inputs Required

The code can be improved heavily inside the repository, but production launch still needs owner-provided external resources.

## Required before real school production use

1. **Domain**
   - Final HTTPS domain for `PUBLIC_BASE_URL`.

2. **Database**
   - Supabase/PostgreSQL `DATABASE_URL`.
   - Preferred production region.
   - Backup/restore policy.

3. **Email provider**
   - Resend, SendGrid, Postmark, or SMTP settings.
   - Verified sender domain.

4. **Payment provider**
   - Checkout URLs for Standard, Pro, and Custom inquiry flow if used.
   - Billing webhook secret.
   - Provider dashboard access for reconciliation.

5. **Legal/company data**
   - Legal company name if registered.
   - Contact email.
   - Support email.
   - Privacy owner.
   - Data retention commitments.
   - Consent approach for minors/students.

6. **Subprocessors**
   - Actual providers used for hosting, database, email, billing, analytics, and optional AI APIs.

## Do not claim publicly until true
- Real paying customers.
- Certified compliance status.
- Medical/diagnostic capabilities.
- Emergency response coverage.
- Legal approval across all countries.
