# Action Integrity

SchoolMind includes `scripts/action_integrity.py` to catch common dead UI patterns.

It checks:

- `href="#"`
- empty `href`
- inline `onclick`
- buttons without explicit `type`
- clickable-looking elements without a real link or JS data hook

Run:

```bash
python scripts/action_integrity.py
```

Visible actions should navigate, save, update, export, send, filter, or clearly show a success/error state.
