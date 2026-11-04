# Roadmap

Every item below has an **on/off switch**, off by default:

```bash
noisycompany features                 # list with state
noisycompany features on doh_sink     # switch on (applies at the next session)
noisycompany features off doh_sink
```

or with the buttons of the local dashboard (`noisycompany features on dashboard`, then
open http://127.0.0.1:9788). Planned items are listed but cannot be switched on yet.
Defaults can also be set in the `[features]` table of the config file.

## Available

| Switch | Milestone | What it does | Cost |
|---|---|---|---|
| `persona_drift` | 2.1 | Main hobby stable for `drift_main_days` (120), secondary interests keep rotating | none |
| `locale_packs` | 2.1 | Adds personas in your language (`fr`, `de`, `es`, `it` packs, chosen in `[features.options] locale_packs`, `locale_share` = 60 % of sessions) | none |
| `metered_guard` | 2.1 | NetworkManager reports a metered link: daily cap drops to the eco budget (3 MB) | saves data |
| `doh_sink` | 2.2 | DNS noise sent over DNS-over-HTTPS (RFC 8484) to `doh_url`, the resolver your browser uses | ~5 KB per lookup instead of ~300 B |
| `metrics` | 2.2 | Prometheus text on http://127.0.0.1:9789/metrics | none |
| `dashboard` | 2.2 | Local page: budget, KPIs, active personas, on/off buttons. Localhost only, anti DNS rebinding, CSRF token, strict CSP | none |
| `labelled_log` | 2.2 | JSONL ground truth of every action (`label: benign-noise`) for SOC / IDS / NDR testing | disk only |
| `privacy_report` | 2.3 | `noisycompany privacy` and a dashboard card: content blocker, encrypted DNS (browser DoH or systemd-resolved DoT), fingerprinting protection, GPC, IPv6 temporary addresses, noise running, noise DNS coherent with browser DNS. Score out of 100, advice for each gap. Read-only, local, no path or browsing data in the output | none |
| `persona_marketplace` | 2.3 | `noisycompany packs [list\|install\|remove\|check]`: reviewed packs shipped in `data/packs/` (photography, board games, knitting, aquariophilie FR), installed by copy, re-validated at load (a tampered pack is ignored). CI rejects packs with sensitive topics, non-HTTPS seeds, seeds outside their domains, login/ads URLs | none |
| `browser_companion` | 2.3 | Firefox WebExtension in `companion/`: rare persona visits from the real browser. Light mode (no cookie, ~100 KB) or tab mode (hidden muted tab in a dedicated container, ~2 MB). Only while the user is active, 2 MB/day cap, host access limited to persona domains. Switched from its own popup. See [companion/README.md](../companion/README.md) | ~2 MB/day max |
| `business_profiles` | 2.4 | Replaces personas with a business profile (`office`, `dev_team`, `retail`), profile written in every labelled-log record: benign traffic with ground truth for SOC labs | none |
| `dns_coherence` | 2.2 | DNS noise looks up the hosts the persona read or saw links to (70 % of lookups), like a browser revisiting | none |
| `weekly_rhythm` | 2.2 | Session gaps follow evening peaks, later mornings on weekends and fixed-date holidays, quieter July-August | none (same cap) |
| `third_party_bursts` | 2.2 | After a page, resolve up to `third_party_max` (4) embedded third-party hosts (scripts, images, fonts, preconnect). DNS only; ad and tracker hosts skipped | ~1.2 KB per page |
| `request_trees` | 3.0 | Fetches up to 3 same-origin CSS/JS per page, once per URL (like a cache), robots.txt checked, half the page cap each | ~+60 % |
| `appliance_packages` | 2.4 | Home Assistant add-on (`deploy/homeassistant/`), `docker-compose.yml` (host network, read-only, no capability), Raspberry Pi installer (`deploy/raspberrypi/install.sh`, eco preset, user service with linger), OpenWrt procd service (`deploy/openwrt/`, state in RAM), multi-arch image on GHCR at each `v*` tag. The switch writes a heartbeat used by `noisycompany health` and the Docker HEALTHCHECK | none |
| `collective_noise` | 3.0 | `noisycompany collective create\|join\|leave\|show`: a short share code (`nc1:...`, ~320 chars) carries a shared salt and a list of **already reviewed** personas, with a SHA-256 digest. Members rotate the same decoys at the same time. No server; a code cannot add domains, so a malicious member cannot steer your traffic to their server | none |
| `separability_study` | research | `noisycompany study --noise labelled.jsonl --human trace.csv`: windows + logistic regression (pure Python), k-fold ROC AUC and the most telling features. See [STUDY.md](STUDY.md) | none |

All items above are implemented (v2.0.0).

## Next evolutions

Each will get its own switch, off by default, like the items above.

### 2.1: hardening and trust (from the November 2026 audit)

These are safety fixes, so they are always on (no switch).

| Item | Why | Status |
|---|---|---|
| Connect to the vetted IP address (custom `HTTPSConnection` with SNI) | Removes the residual check-then-connect window of the public-IP check | Done |
| Keyless signed provenance for GHCR images (Sigstore, GitHub attestations) | Users can verify the image before running it on a home appliance | Done, from the next tag |
| Fuzzing of the link parser, body decoder and share-code decoder | All parse untrusted input | Done: seeded fuzz tests in CI, optional atheris harness in `fuzz/` |
| Home Assistant add-on as non-root | Least privilege on the always-on box | Done (uid 10001). AppArmor profile still to do |
| Publish on PyPI (trusted publishing) | `pipx install noisycompany` without git | Workflow ready, waits for the PyPI trusted publisher |

### 2.2: realism (driven by `noisycompany study` results)

| Item | Why | Status |
|---|---|---|
| Interest coherence across DNS and HTTP: lookups follow the pages actually read | Today DNS sessions and page reads are independent | Done: `dns_coherence` |
| Seasonal / weekly rhythm (weekends, holidays, evenings) | Hour and weekday are telling features | Done: `weekly_rhythm` (household-wide, not per persona yet) |
| `Accept-Language` per locale, more locales (de, es, it) | Locale mismatch is a tell | Done: packs `de`, `es`, `it` |
| Third-party host bursts (opt-in, still capped) | Real page loads resolve dozens of hosts; the study shows it is the main giveaway | Done: `third_party_bursts` |
| Study: Pi-hole direct import, weekday feature | A stronger observer model | Done (FTL database, AdGuard query log, `day_off`). Packet sizes and TLS fingerprint still open: DNS traces do not carry them |

### 2.3: browser companion

| Item | Why |
|---|---|
| Signed build on addons.mozilla.org | Normal install, automatic updates |
| Chromium MV3 port (Chrome, Brave, Edge) | Most users |
| Companion reads the daemon's dashboard switches (opt-in localhost link) | One place to control everything |
| Optional "default container" tab mode with explicit warning | Dilutes the user's own cookie profile, for those who want it |

### 2.4: appliances and integrations

| Item | Why |
|---|---|
| Pi-hole / AdGuard Home plugin (noise from the resolver box, study from its log) | Best place for DNS noise and for measurement |
| Umbrel / CasaOS / TrueNAS / Unraid app templates | One-click installs |
| OpenWrt `.ipk` package with LuCI page | Routers without manual copy |
| Grafana dashboard JSON for the Prometheus metrics | Home-lab users |
| Dashboard in French (i18n) and accessibility audit | Wider audience |

### 3.x: research and collective

| Item | Why |
|---|---|
| Collective share code as QR code, expiry and rotation of the shared salt | Easier and safer sharing |
| Public separability benchmark (synthetic traces, published AUCs per release) | Measure progress honestly |
| Real energy measurement (RAPL / smart plug) published in IMPACT.md | Replace estimates by measurements |
| Business profiles for more sectors + scenario files for SOC exercises | Detection engineering market |

## Use cases enabled

- Home privacy box (Pi, NAS, router), alongside Pi-hole / AdGuard Home.
- Public Wi-Fi hygiene on laptops with `metered_guard` and the eco preset.
- Detection engineering: `labelled_log` + `metrics` give realistic benign traffic with
  ground truth for IDS / NDR / SIEM tests (beaconing and DNS-anomaly rules must not fire).
- Honeypot realism: a decoy host that "lives".
- Teaching: `noisycompany estimate` + the threat model as a workshop on what an ISP sees.
- Research datasets on traffic classification.

## Product ideas

See [OPPORTUNITIES.md](OPPORTUNITIES.md): appliance distribution, privacy score, B2B
benign-traffic generator for SOC testing, persona API for researchers, collective noise.
