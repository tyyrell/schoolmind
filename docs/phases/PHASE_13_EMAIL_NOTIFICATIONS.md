# Phase 13 — Email Notifications Readiness

Phase 13 turns SchoolMind AI email handling into a more reliable transactional outbox layer.

## What changed

- Added centralized transactional templates for workspace invites, password resets, sales leads, trial starts, and test email.
- Added message type, metadata, attempt count, last error, last attempt time, and update time to the outbox schema.
- Added delivery health reporting for queue, console, and SMTP modes.
- Added a test-email queue action in the school admin outbox.
- Changed queue-only behavior so dispatch does not pretend to send email.
- Added outbox UI warnings so admins know when email is not production-ready.

## Email delivery is not fake

`EMAIL_DELIVERY_MODE=queue` stores messages only. It is safe for demo and review, but it does not deliver email.

`EMAIL_DELIVERY_MODE=console` prints messages for local QA only.

`EMAIL_DELIVERY_MODE=smtp` is the only production-ready delivery mode in this build, and it requires SMTP settings.

## Required production inputs

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME` if your provider requires authentication
- `SMTP_PASSWORD` if your provider requires authentication
- `SMTP_FROM`
- `TEST_EMAIL_RECIPIENT`

Recommended providers include Resend SMTP, Postmark SMTP, SendGrid SMTP, Mailgun SMTP, or any transactional SMTP provider approved for the school deployment.

## Remaining boundary

This phase prepares delivery infrastructure. It does not create a provider account, verify domains, configure SPF/DKIM/DMARC, or guarantee deliverability. Those are owner tasks before production.
