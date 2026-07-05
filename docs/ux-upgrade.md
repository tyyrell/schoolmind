# Global UX Upgrade

This pass upgrades SchoolMind from a mostly visual demo into a connected school-support workflow.

## Added

- Persistent account settings for every school role.
- Platform-owner account preferences.
- Public guest language/theme preferences.
- First-visit personalization onboarding for guests and signed-in users.
- Mobile drawer navigation with active states and independent scroll.
- RTL rendering for Arabic.
- Nour chat API with saved conversation state, consent checks, CSRF, plan limits, and support-signal routing.
- Student progress hub.
- Weekly wellbeing summary.
- Support-plan history.
- Expanded game catalog with filters and saved practice scores.
- Interactive activity controls for the game catalog.
- Resource library filters.
- Help Center, Activity Center, and Admin Plan Limits.
- Backup export coverage for user preferences.

## Verification

Run:

```bash
python -m compileall -q .
python run_tests.py
python scripts/audit.py
python scripts/route_audit.py
python scripts/build_release.py
```
