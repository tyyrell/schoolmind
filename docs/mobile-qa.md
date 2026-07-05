# Mobile QA

## Covered Widths

The CSS is designed for:

- 360px
- 390px
- 414px
- 768px
- desktop

## Behavior

- Public navigation opens as a scrollable drawer.
- Workspace navigation opens as an independent role-aware drawer.
- Long menus scroll inside the drawer instead of pushing the whole page.
- Dashboard cards stack into one column.
- Forms use full-width actions on small screens.
- Nour keeps the composer sticky near the bottom of the chat panel.
- Settings use horizontal section tabs that scroll safely on small screens.

## Automated Checks

Run:

```bash
python scripts/route_audit.py
python scripts/action_integrity.py
python run_tests.py
```

Manual browser QA should still include at least one phone-width pass through login, settings, Nour, games, student dashboard, admin billing, and platform account settings.
