# Security Notes

Implemented in this build:

- CSRF token validation on mutating forms
- Role guards for every internal workspace
- Tenant-scoped database queries
- Parameterized SQL
- No-store cache headers for dashboards
- X-Frame-Options DENY
- Content Security Policy
- CSV injection protection
- Audit event table
- Session cookie hardening

Still required before real school deployment:

- External security review
- Formal incident response process
- Data processing agreement
- Backup and restore testing
- Email verification
- Password reset flow
- Optional two-factor authentication
