# NoisyCompany browser companion (Firefox)

The daemon cannot look like your browser: it has its own TLS stack and no request tree.
The companion makes the same kind of rare, persona-coherent visits **from Firefox
itself**, so at network level they are indistinguishable from your own browsing.

**Off by default.** Turn it on from the toolbar popup.

## Modes

| Mode | What happens | Cost per visit | Acts on |
|---|---|---|---|
| Light (`fetch`, default) | Background request with Firefox's network stack, **no cookie**, redirects not followed, page cut at 192 KB, only links on persona domains are followed | ~100 KB | ISP, Wi-Fi, DNS resolver (same TLS fingerprint as you) |
| Tab | Hidden, muted tab in a dedicated **NoisyCompany container**, closed after 20-60 s | ~2 MB | Trackers on the visited page build a *separate* decoy profile; your own cookies are not touched |

Neither mode clicks anything, loads ads on purpose, fills forms or logs in. Your content
blocker keeps working in tab mode. Visits only happen while you are active at the
computer (`idle` API), on average one every 25 minutes, under a daily cap (2 MB).

## Options (popup)

- **Persona languages**: en (built-in), fr, de, es, it. Default en + fr.
- **Tab container** (tab mode, Firefox): the separate NoisyCompany container (default),
  or your **default container**, after a warning. The second one adds the decoy
  interests to *your* own cookie profile: that dilutes your real ad profile, but sites
  then also see those visits as yours.
- **Follow the daemon's switch**: the companion turns on and off with the daemon's
  `browser_companion` switch (CLI or dashboard). It reads
  `http://127.0.0.1:9788/api/status` (read-only); Firefox asks for that localhost
  permission when you tick the box. If the daemon does not answer, the popup switch
  applies.

## Chromium (Chrome, Brave, Edge)

`cd companion && npm run build`, then `chrome://extensions` > Developer mode > *Load
unpacked* > `companion/build/chromium`. Light mode only: Chromium has no containers, so
a tab would carry your own cookies.

## Honest scope

- Light mode does not change ad profiles built from cookies: there are no cookies.
- Tab mode feeds a separate container, so it does not dilute *your* cookie profile; it
  can still confuse trackers that link profiles by IP + fingerprint.
- The best protection against targeted ads remains a blocker. See
  [../docs/THREAT_MODEL.md](../docs/THREAT_MODEL.md).

## Install (development)

1. `npm run build`, then `about:debugging#/runtime/this-firefox` > *Load Temporary Add-on* >
   `companion/build/firefox/manifest.json`.
2. Click the NoisyCompany toolbar icon, switch it on.

A signed build on addons.mozilla.org comes from the release workflow once the AMO keys
are set (job `amo`).

## Permissions

`alarms`, `storage`, `idle`, `contextualIdentities` + `cookies` (container for tab
mode, Firefox only), and host access **only** to the persona domains (no `<all_urls>`,
no `tabs`). Optional, asked at the click: `http://127.0.0.1/*` for the daemon link.
No data leaves the extension; the visit log (last 20) stays in local storage.

## Development

```bash
noisycompany companion export   # regenerate personas.js + manifest.json from the reviewed personas
cd companion && npm test && npm run check
```
