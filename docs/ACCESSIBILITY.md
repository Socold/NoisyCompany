# Accessibility audit of the local dashboard (2.4)

Scope: `http://127.0.0.1:9788` (`data/dashboard.*`), in English and French
(`?lang=fr`, or the browser language). Checked against WCAG 2.2 AA by reading the code and
rendering it in a headless Chromium.

| Check | Before | Now |
|---|---|---|
| Page language | Always `en` | `lang` follows the UI language |
| Keyboard focus | The 10 s refresh rebuilt the switch list and dropped the focus | Switches updated in place, focus kept |
| Switch names | `aria-label` = title only | `aria-labelledby` title + `aria-describedby` description |
| Status changes | Silent | Budget and state in `aria-live="polite"` regions |
| Errors | `alert()` pop-up | Inline `role="alert"` message |
| Budget meter | Percentage only | `aria-valuetext` "1.2 MB / 3 MB" |
| Skip link | None | "Skip to the switches" |
| Motion | Animated bar | Disabled with `prefers-reduced-motion` |
| Contrast (light / dark) | | Text 5.3:1 / 6.1:1, accent button 5.9:1, "TO DO" red 5.6:1: AA |
| Visible focus | Switches only | Unchanged, all buttons are native and focusable |

Still open: the browser companion popup (same review planned), and translations of the
CLI output (French is dashboard-only).
