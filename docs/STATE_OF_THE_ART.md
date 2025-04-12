# State of the art (November 2026)

## Noise and obfuscation tools

| Tool | Type | Layer | Status | Strengths | Weaknesses |
|---|---|---|---|---|---|
| [1tayH/noisy](https://github.com/1tayH/noisy) | Python script | DNS + HTTP | Unmaintained since 2023 (~1.7k stars) | Simple, Docker | Uniform random crawl, rotating UAs, full downloads, no budget, adult/piracy defaults, `requests` dependency, recursion |
| [madereddy/noisy](https://github.com/madereddy/noisy) | Fork | DNS + HTTP | Docker-oriented, modernised Python | Packaging | Same design |
| [zachey01/noisyjs](https://github.com/zachey01/noisyjs) | JS port | HTTP | Last push 2024 | Node | Same design |
| [essandess/isp-data-pollution](https://github.com/essandess/isp-data-pollution) | Python + headless browser | HTTP (full browser) | Low activity | Real browser fingerprint, bandwidth cap | Heavy (Chromium/Selenium, ~50 GB/month default), high CPU/energy |
| TrackMeNot | Browser extension | Search queries | Removed from Chrome store (2019), Firefox only | Targets search profiles | Queries distinguishable by classifiers (Peddinti & Saxena, 2010) |
| AdNauseam | Browser extension (uBlock fork) | Ads | Active, Firefox | Acts where ad targeting happens | Clicks ads (click-fraud debate), banned from Chrome store, extra traffic |
| Noiszy, Internet Noise, Track This (Mozilla, 2019), Fauxx | Extensions / web pages | Browser tabs | Mostly abandoned or one-shot | Easy | Opens real tabs, random, not continuous |
| PartyLoud | Bash | HTTP | Small project | Minimal | Random, no politeness |

## Protection tools (block rather than hide)

| Tool | What it does | Relation to NoisyCompany |
|---|---|---|
| uBlock Origin, Privacy Badger | Block trackers in the browser | **First line** against targeted ads; NoisyCompany does not replace them |
| Firefox resistFingerprinting, Brave farbling, Mullvad Browser, Tor Browser | Make fingerprints uniform or random | Against recognition; out of NoisyCompany's scope |
| DoH / DoT / ODoH, ECH | Hide DNS and SNI from the network | Reduce what noise must hide; complementary |
| VPN, iCloud Private Relay, Tor | Move the observer elsewhere | Strongest against ISP; noise still useful at the exit/resolver |
| Pi-hole, NextDNS, AdGuard Home | Network-wide blocking | Natural host for NoisyCompany (see opportunities) |

## Research takeaways

- Brunton & Nissenbaum, *Obfuscation: A User's Guide for Privacy and Protest* (MIT Press,
  2015): obfuscation is legitimate when the user has no way to opt out; its value depends
  on the adversary not being able to filter it.
- Peddinti & Saxena (PETS 2010) and later work: TrackMeNot queries could be separated from
  real ones with high accuracy using machine learning. **Lesson: uniform or generic noise
  is filterable; coherence and realism matter.**
- Howe & Nissenbaum, *Engineering Privacy and Protest: a Case Study of AdNauseam* (IWPE
  2017): in-browser obfuscation acts where profiling happens, at a legal and ethical cost.
- Website-fingerprinting and traffic-classification literature: TLS fingerprints
  (JA3/JA4), request trees (a real page load triggers dozens of sub-requests) and timing
  separate bots from humans. A stdlib crawler will not look like a browser to a
  determined classifier; it can look like a person's interests to a hostname classifier.

## Verdict: rewrite or adopt?

No existing project is strictly better for the stated goals (very light, no bandwidth
disturbance, harder to filter, anti-profiling):

- **isp-data-pollution** is more realistic per request (real browser) but one to two
  orders of magnitude heavier: incompatible with the ecological constraint.
- **AdNauseam** is the only tool acting on ad targeting, but it is a browser extension
  with a different scope and a legal grey zone.
- **noisy forks** keep the original's design flaws.

Decision: **new code base**, keeping NoisyCompany's idea (background DNS + HTTP noise) and
adding personas, budget, netwatch, scheduling, politeness and impact estimation. An
optional, lightweight browser companion (in-browser noise with your real fingerprint, no
ad clicks) is the logical next step to act on ad profiling: see
[OPPORTUNITIES.md](OPPORTUNITIES.md).
