# Security

## Authentication

- Users authenticate with email/password or Google OAuth when configured.
- Passwords are hashed with Werkzeug.
- Sessions expire after eight hours.
- Repeated failed login attempts lock user and platform-admin accounts for 15 minutes.
- Password reset and invite flows use hashed random tokens with expiry.

## Authorization

- `role_required` protects student, teacher, counselor, admin, and billing routes.
- `platform_required` protects the SaaS operator console.
- Account settings routes require active sessions and use CSRF for profile, preference, notification, and password updates.
- Personalization preferences use CSRF and save only display/accessibility choices.
- School users are scoped by `school_id`.
- Suspended, cancelled, past-due, and expired-trial workspaces are blocked except for admin billing recovery routes.

## Web Security

- CSRF tokens are required for POST/PUT/PATCH/DELETE form actions.
- Security headers include CSP, `X-Frame-Options`, `X-Content-Type-Options`, Referrer Policy, Permissions Policy, COOP, and production HSTS.
- Protected workspace and export routes set `Cache-Control: no-store`.
- Sensitive routes have in-memory rate limits.
- Nour chat API requires student role, CSRF header, guardian consent when enabled, and active plan daily limits before saving messages.
- Action integrity checks block placeholder links, missing button types, and clickable-looking controls without a real link or JS hook.

## Payments

- Provider webhooks require `X-SchoolMind-Signature`, an HMAC-SHA256 of the raw body using `BILLING_WEBHOOK_SECRET`.
- Webhook writes are transactional.
- Manual activation is intended only after confirmed offline/provider payment.

## Secrets

- Do not commit `.env`.
- Rotate `SECRET_KEY`, `PLATFORM_ADMIN_PASSWORD`, SMTP credentials, Google OAuth secrets, and billing webhook secrets through the hosting provider.
- After rotating `SECRET_KEY`, existing sessions and CSRF tokens become invalid; schedule this during low-traffic windows.

## Monitoring

- Request logs are structured JSON and include request id, method, path, status, elapsed time, and remote address.
- Use platform log drains or a log provider to collect stdout/stderr.
- `LOG_LEVEL`, `ENABLE_REQUEST_LOGGING`, and `REQUEST_ID_HEADER` control logging behavior.

## Known Residual Risks

- In-memory rate limiting is per-process and should be replaced with Redis or provider-level rate limiting for high-scale production.
- SQLite requires disciplined persistent disk backup.
- External legal/security review is required before real student deployment.
