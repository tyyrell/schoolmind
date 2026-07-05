# Incident Response

## First Actions

1. Identify whether the issue affects auth, billing, data, email, or deployment.
2. Preserve logs and do not delete the persistent database disk.
3. Disable public trials from `/platform/settings` if signup abuse is involved.
4. Suspend affected school tenants from `/platform/schools/<id>` if needed.
5. Rotate impacted secrets through the hosting provider.

## Auth Incident

- Force password resets for affected users from the Admin Security Center.
- Unlock accounts only after verifying the user.
- Rotate `SECRET_KEY` if session integrity is suspected to be compromised.
- Review `account_security_events`.

## Billing Incident

- Temporarily remove provider webhook URL or rotate `BILLING_WEBHOOK_SECRET`.
- Check `billing_events`, `subscriptions`, `payment_intents`, and `coupon_redemptions`.
- Reconcile with the payment provider dashboard before manual activation.

## Database Incident

- Stop writes by pausing the service if corruption is suspected.
- Copy the persistent database file before attempting repair.
- Follow `docs/BACKUP_RESTORE_RUNBOOK.md`.
- Run tests and route audit after restore.

## Deployment Incident

- Roll back to the previous ZIP or commit.
- Keep the persistent disk attached.
- Run `/api/health` and `/api/readiness`.
- Sign in as platform admin and verify school status, billing, and user counts.

## Secret Rotation

- Rotate one secret at a time where possible.
- Record the rotation time.
- Restart the service.
- Verify login, password reset, billing webhook, and email delivery.

