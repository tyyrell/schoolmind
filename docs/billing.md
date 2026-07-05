# Billing

## Plans

Plans are defined in `schoolmind/config.py`:

- Starter
- Growth
- Scale

Each plan includes student/staff limits and feature text.

## Checkout

Set checkout URLs through:

- `CHECKOUT_STARTER_URL`
- `CHECKOUT_GROWTH_URL`
- `CHECKOUT_SCALE_URL`

If a checkout URL is missing, admins can still record manual activation after an offline/provider-confirmed payment.

## Manual Activation

Admins can activate a plan from `/admin/billing` after confirming payment externally. Manual activation:

- Validates coupon code if provided.
- Creates a subscription row.
- Updates school plan and status.
- Creates a payment-intent row.
- Creates a billing event.
- Records coupon redemption when applicable.

## Provider Webhook

Endpoint:

```txt
POST /api/billing/webhook
```

Headers:

```txt
X-SchoolMind-Signature: hmac_sha256(raw_body, BILLING_WEBHOOK_SECRET)
```

Supported payload fields:

- `school_slug`
- `plan`
- `status`: `active`, `past_due`, `cancelled`, or `trialing`
- `event_type`
- `provider_reference`
- `amount`

Webhook writes are transactional and update school status, subscription records, billing events, and payment intents.

## Coupons

Platform admins manage coupons at `/platform/coupons`.

Coupons support:

- Code uniqueness.
- Discount percentage.
- Max redemptions.
- Plan scope.
- Expiration date.
- Active/disabled status.

## Required Reconciliation

Before marking real revenue as final, reconcile `billing_events` and `payment_intents` with the payment provider dashboard.

