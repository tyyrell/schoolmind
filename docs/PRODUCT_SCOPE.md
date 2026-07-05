# Product Scope

## Positioning

SchoolMind is a school support SaaS for educational wellbeing indicators and counselor workflows. It must not be marketed as diagnosis, therapy, emergency response, or medical advice.

## Paid SaaS modules included

- Public landing page
- Pricing page
- 30-day trial onboarding
- Tenant school creation
- Subscription table and billing screen
- Environment-driven checkout URLs
- Manual billing activation for offline/provider-confirmed payments
- Billing event timeline
- Role-based login
- Invite token onboarding
- Outbox email queue for provider integration
- Password reset flow using secure reset tokens
- Student check-ins
- Student wellbeing studio with eight-domain scan
- Automatic non-diagnostic student support plans
- Student private journal
- Student support requests
- Student Nour companion reflection workflow
- Student Nour chat API with saved conversation state and plan limits
- Student progress hub
- Student weekly wellbeing summary
- Student support-plan history
- Persistent account preferences for language, theme, font size, reduced motion, high contrast, dyslexia-friendly display, and notifications
- First-visit personalization onboarding
- Mobile drawer navigation with role-aware links
- Help Center and Activity Center
- Admin School Plan Limits page
- Interactive game activities with saved progress
- Public guest language/theme preferences
- Teacher aggregate class pulse with stress, sleep, belonging, and workload patterns
- Counselor alert triage
- Counselor focus queue
- Counselor student support brief
- Counselor student detail view with scans and plans
- Counselor-authored support plans
- Counselor playbooks
- Intervention notes
- Admin launch checklist
- Admin user management
- Bulk CSV user import
- Consent center
- School policy/settings page
- Sales lead capture from contact form
- Audit log
- CSV export with latest wellbeing focus
- JSON workspace export with assessments and support plans
- JSON workspace export with user preferences
- Health and readiness APIs
- Invite-only deployment controls through environment variables
- Render deployment files with persistent disk config
- Tests, audit script, and production preflight script
- Action integrity and translation coverage scripts

## Not included yet

- Full payment provider account setup
- Email delivery provider account setup
- Clinically validated scoring study
- Country-specific legal policy pack
- External security penetration test
- PostgreSQL data layer

## Recommended next phases

1. Connect checkout links from a payment provider that supports the business country and target markets.
2. Add email delivery for invites, support notifications, and password reset.
3. Add provider webhooks if the payment provider supports them cleanly.
4. Migrate to PostgreSQL before serious production usage.
5. Run external security and legal review.
