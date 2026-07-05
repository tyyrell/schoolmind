# Themes

SchoolMind themes are driven by CSS variables on the `<html data-theme>` attribute.

## Themes

- `light`
- `dark`
- `midnight`
- `calm-blue`
- `soft-green`
- `high-contrast`

The active theme is stored in `user_preferences`, `platform_admin_preferences`, or the guest session. High contrast can override the chosen theme by rendering `data-theme="high-contrast"`.

## Accessibility

The UI also supports:

- font size: `small`, `normal`, `large`, `xl`
- reduced motion
- dyslexia-friendly font mode
- Arabic RTL

These are server-rendered so the first page load uses the saved preference.
