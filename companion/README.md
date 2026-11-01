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

## Honest scope

- Light mode does not change ad profiles built from cookies: there are no cookies.
- Tab mode feeds a separate container, so it does not dilute *your* cookie profile; it
  can still confuse trackers that link profiles by IP + fingerprint.
- The best protection against targeted ads remains a blocker. See
  [../docs/THREAT_MODEL.md](../docs/THREAT_MODEL.md).

## Install (development)

1. `about:debugging#/runtime/this-firefox` > *Load Temporary Add-on* > `companion/src/manifest.json`.
2. Click the NoisyCompany toolbar icon, switch it on.

A signed build on addons.mozilla.org is planned.

## Permissions

`alarms`, `storage`, `idle`, `contextualIdentities` + `cookies` (container for tab
mode), and host access **only** to the persona domains (no `<all_urls>`, no `tabs`).
No data leaves the extension; the visit log (last 20) stays in local storage.

## Development

```bash
noisycompany companion export   # regenerate personas.js + manifest.json from the reviewed personas
cd companion && npm test && npm run check
```
