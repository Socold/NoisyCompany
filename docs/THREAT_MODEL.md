# Threat model

Noise only helps against an observer that **sees your traffic but cannot tell which part
is you**. Who can tell decides everything.

## Observers and what they see

| Observer | Sees | Can it separate NoisyCompany from you? | NoisyCompany's effect |
|---|---|---|---|
| ISP / mobile carrier | DNS queries (unless encrypted), TLS SNI hostnames, IPs, volumes, timing | Partly: different TLS fingerprint (JA3/JA4) than your browser, no third-party sub-requests | **Useful**: hostname-level profile diluted with coherent decoy interests |
| Public Wi-Fi, hotel, router vendor, smart TV-style "network analytics" | Same as ISP | Same | **Useful** |
| DNS resolver you use (ISP, Google, Cloudflare...) | Every hostname you resolve | Hard: lookups go through the same resolver as yours | **Most useful**: DNS noise is cheap and blends well |
| Ad-tech / trackers in the browser (cookies, fingerprint, login) | What you do in the browser | **Yes, trivially**: NoisyCompany is not your browser, carries none of your cookies | **None**. Use a blocker. |
| Platforms you are logged into (Google, Meta, Amazon...) | Everything you do there | Yes | **None** |
| Data brokers buying ISP data (where legal, e.g. US) | ISP-level data | Partly | **Useful** |
| Targeted, motivated adversary (state, stalker) | Everything above, with effort | Yes, with traffic analysis | **None**. Use Tor / a trusted VPN. |

## What NoisyCompany protects against

- **Network-level interest profiling**: the "this household visits fishing, baby and
  loan sites" inference that ISPs, Wi-Fi operators and brokers make from hostnames.
- **DNS-based profiling** by your resolver.
- **Cheap categorisation**: hostname classifiers now see several plausible, stable
  interests that are not yours.

## What NoisyCompany does not protect against

- **Targeted ads driven by browser tracking** (cookies, pixels, fingerprinting, logged-in
  accounts). This is where most ad targeting happens and the daemon does not touch it.
  Countermeasures: uBlock Origin, Firefox/Brave/Mullvad Browser with fingerprinting
  protection, container tabs, logging out. The [Firefox companion](../companion/README.md)
  helps at the margin. Its light mode gives the noise your browser's network fingerprint.
  Its tab mode feeds trackers a *separate* decoy profile in its own container. Neither
  dilutes your own cookie profile.
- **Recognition / re-identification** across sites: noise does not change your fingerprint.
- **Content inspection** of HTTPS: nobody but the endpoint sees it anyway.
- **Traffic analysis by a determined adversary**: NoisyCompany's requests have their own TLS
  stack and timing signature. Honest estimate: a dedicated classifier would separate a
  large part of them. Research on TrackMeNot showed the same for search noise.
- **Anything from the sites NoisyCompany visits**: they see your IP make a visit. That is the point.

## Design choices that follow

- **Encrypted DNS + ECH reduce what the ISP sees more than noise does.** If you can enable
  DoH/DoT and ECH, do it; NoisyCompany then mostly targets your resolver.
- **Coherent personas** instead of random URLs: random noise is removed by filtering
  hostnames visited once. Personas revisit the same domains over days.
- **One fixed, current user agent**: rotating UAs per request is a signal by itself.
- **No sensitive topics**: noise must never make an observer believe something harmful
  about you (health, sexuality, religion, politics, crime, debt). The original project
  included adult and piracy sites in its defaults; this one does not.
- **No ad clicks**: click injection (as AdNauseam does) costs advertisers money, is
  arguably click fraud, and got AdNauseam banned from the Chrome Web Store.

## Protections against abuse of NoisyCompany itself

| Threat | Protection |
|---|---|
| A persona site is compromised and redirects to your router / NAS (SSRF) | Every URL and every redirect hop must be http(s), inside the persona's domains, and resolve **only** to public IPs (`Fetcher.url_allowed`); the companion does not follow redirects |
| DNS rebinding of a persona domain to a LAN address | Same public-IP check on every resolution (cached 10 min) |
| Decompression bomb or huge page | 192 KB read cap, 2 MB inflate cap, HTML only, nothing executed |
| A web page you visit drives the local dashboard (CSRF, DNS rebinding) | 127.0.0.1 only, strict `Host` and `Origin` checks, per-process token, strict CSP |
| A malicious collective member steers your traffic to their server to learn your IP | Share codes can only name reviewed personas; digest-checked; size-capped |
| A tampered persona pack adds sensitive or tracking domains | Packs re-validated at load; CI validator rejects sensitive topics and out-of-scope seeds |
| Other local users read your state (salt, collective secret) | umask 077, state directory 0700 |
| Supply chain | Zero runtime dependency; CI actions pinned by SHA; non-root, read-only image; GHCR image with SBOM and provenance |

Full audit: [SECURITY_AUDIT_2026-11.md](SECURITY_AUDIT_2026-11.md). Data inventory:
[PRIVACY.md](PRIVACY.md).

## Risks for the user

- Your IP visits the decoy sites. Keep personas harmless (enforced for built-ins).
- On a monitored network (employer, school), the traffic is attributable to you.
- Bandwidth on metered links: use `eco`, lower `daily_mb`.
