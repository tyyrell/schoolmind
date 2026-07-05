# Testing

## Local Commands

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python run_tests.py
python scripts/audit.py
python scripts/route_audit.py
python scripts/action_integrity.py
python scripts/i18n_report.py
```

Run `python scripts/preflight.py` with production-like environment variables before deployment.

## Release Commands

```bash
python scripts/clean_release.py
python scripts/release_check.py
python scripts/build_release.py
```

## Test Coverage

The integration suite covers:

- Public pages.
- Signup and terms acceptance.
- Login, password reset, lockout, and admin unlock.
- Google OAuth disabled-state safety.
- Role boundaries and tenant suspension.
- Student wellbeing scans, journals, Nour, goals, games, and breathing sessions.
- Student account preferences, public guest language/theme, Nour chat API, progress hub, weekly summary, support plans, and game filters.
- First-visit personalization onboarding, dismiss flow, guest save flow, authenticated database persistence, interactive game controls, Help Center, Activity Center, and Admin Plan Limits.
- Counselor case actions and escalation email queue.
- Admin users, invites, imports, consent, outbox, security, operations, backups, and retention.
- Billing manual activation, coupon discounting, provider webhook activation, and cancellation state.
- Platform admin school status, account preferences, coupons, and public-site settings.

Current suite size: 51 tests.

## CI

GitHub Actions runs install, compile, tests, audit, production preflight, route audit, action integrity, translation coverage, cleanup, and release scan.
