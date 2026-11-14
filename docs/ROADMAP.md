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
| `page_load_bursts` | 3.1 | Third-party bursts the size of a real page load: 5-25 hosts (`burst_hosts`) within about a second, embedded hosts first, then hosts the persona already read | DNS only |
| `interleave_with_user` | 3.1 | Sessions start mostly while the local traffic counter shows you online (`interleave_active_kbps`), rarely otherwise (`interleave_idle_share`) | none |
| `browser_dns` | 3.2 | Lookups behave like a browser's: per-host cache (2-10 min TTL), HTTPS record (type 65) asked next to A/AAAA | ~160 B per new host, fewer repeats |
| `household_masking` | 3.2 | Virtual household of `household_members` (2-5) drawn from the salt: own hobbies, own hours (chronotype shift), sometimes online together, redrawn every `household_reshuffle_days` (30-90). Activity floor `household_floor` (0.35) during active hours hides empty-home periods. Overrides `interleave_with_user` | none (same daily cap) |
| `real_third_parties` | 3.3 | Replays, DNS only, the hosts a real browser contacted when opening each persona site (`data/third_parties.json`: headless Chromium, trackers removed, refreshed monthly), in the recorded order and spacing; also after 60 % of DNS-only site lookups | DNS only, ~300 B per host |
| `separability_study` | research | `noisycompany study --noise labelled.jsonl --human trace.csv`: windows + logistic regression (pure Python), k-fold ROC AUC and the most telling features. See [STUDY.md](STUDY.md) | none |

All items above are implemented (v2.0.0 to v2.2.0).

## Shipped in 2.1.0

- **2.1 hardening** (always on, no switch): sockets pinned to the vetted public IP,
  seeded fuzz tests in CI (+ atheris harness), Home Assistant add-on as uid 10001,
  Sigstore-signed provenance for GHCR images, PyPI trusted-publishing job.
- **2.2 realism**: switches `dns_coherence`, `weekly_rhythm`, `third_party_bursts` (see
  the table above), `de` / `es` / `it` locale packs, study imports of Pi-hole and
  AdGuard Home logs with a `day_off` feature.
- **2.3 companion**: Chromium port (Chrome, Brave, Edge; light mode only), persona
  languages in the popup, opt-in link to the daemon's switch, tab mode in the default
  container behind a warning, AMO signing job.
- **2.4 integrations**: Pi-hole / AdGuard Home box, Umbrel / CasaOS / TrueNAS / Unraid
  templates, OpenWrt package with a LuCI page, Grafana dashboard, French dashboard and
  accessibility fixes.
- **3.x research**: QR share codes with expiry and salt rotation, offline separability
  benchmark published per release, measured energy, three more business sectors and
  SOC scenarios.

## Next evolutions

Each will get its own switch, off by default, like the items above.

### Done in 3.3

- `real_third_parties`: recorded page loads per persona site, same method as HTTP
  Archive's crawl at our scale (HTTP Archive's raw tables are only on BigQuery).

### Done in 3.2 (released as 2.2.0)

- `browser_dns`: lookup cache with per-host TTL, HTTPS-record (type 65) queries.
- `household_masking`: virtual household (2-5 members, own hours and hobbies, overlap),
  activity floor during active hours.

### Next for realism

- HTTPS noise with a browser TLS fingerprint: left to the companion by default, optional
  `browser-tls` extra (curl-impersonate) for headless installs.
- Follow the channel the household uses: DoH when it uses encrypted DNS (privacy report
  already detects it), SNI-only connections then.
- A head-count probe in the benchmark, to measure `household_masking`.

### Done in 3.1 (carried over)

- Per-persona rhythm (`rhythm` windows in personas, with `weekly_rhythm`).
- Page-load bursts (`page_load_bursts`) and noise interleaved with your browsing
  (`interleave_with_user`). Benchmark 0.97 -> 0.95.
- Accessibility of the companion popup (tested statically in CI) and French CLI
  messages (`LANG=fr`, `NOISYCOMPANY_LANG=fr`).
- OpenWrt packages built from each pull request with the official SDK (24.10 `.ipk`).
- AppArmor profile for the Home Assistant add-on: draft, parsed in CI, not active
  until tried on a Supervisor (`deploy/homeassistant/apparmor/`).
- `noisycompany study --pcap`: packet sizes and TLS ClientHello shape per flow. Result:
  daemon HTTPS is identifiable by its Python TLS fingerprint.

### Carried over from 2.1 / 2.2

| Item | Why |
|---|---|
| PyPI publication | Needs the PyPI trusted publisher, then `PYPI_PUBLISH=true` |
| Submit app templates to the Umbrel / CasaOS stores, OpenWrt 25.12 `apk` packages | Store accounts and reviews; 25.12 changed the package format |
| RAPL and smart-plug numbers from several machines in IMPACT.md | One CPU-time measurement so far |
| Browser-like TLS for daemon web noise, or HTTP noise left to the companion | `study --pcap` shows the Python TLS fingerprint gives it away |

### 2.3: browser companion

| Item | Why | Status |
|---|---|---|
| Signed build on addons.mozilla.org | Normal install, automatic updates | Job ready (`amo`), waits for AMO API keys and `AMO_SIGN=true` |
| Chromium MV3 port (Chrome, Brave, Edge) | Most users | Done: `npm run build`, light mode only (no containers). Chrome Web Store listing by hand |
| Companion reads the daemon's dashboard switches (opt-in localhost link) | One place to control everything | Done: follows `browser_companion` |
| Optional "default container" tab mode with explicit warning | Dilutes the user's own cookie profile, for those who want it | Done (Firefox) |
| Persona languages in the companion | Same locales as the daemon | Done: en, fr, de, es, it |

### 2.4: appliances and integrations

| Item | Why | Status |
|---|---|---|
| Pi-hole / AdGuard Home integration (noise from the resolver box, study from its log) | Best place for DNS noise and for measurement | Done: `deploy/pihole/` (compose, config, study on a copy of the FTL database). A real Pi-hole web-UI plugin does not exist as an extension point |
| Umbrel / CasaOS / TrueNAS / Unraid app templates | One-click installs | Done: `deploy/apps/`. Submission to the official stores still to do |
| OpenWrt `.ipk` package with LuCI page | Routers without manual copy | Done: `deploy/openwrt/package/` (UCI, LuCI form). Not built in CI (needs the SDK) |
| Grafana dashboard JSON for the Prometheus metrics | Home-lab users | Done: `deploy/grafana/`, metric names tested |
| Dashboard in French (i18n) and accessibility audit | Wider audience | Done: see [ACCESSIBILITY.md](ACCESSIBILITY.md) |

### 3.x: research and collective

| Item | Why | Status |
|---|---|---|
| Collective share code as QR code, expiry and rotation of the shared salt | Easier and safer sharing | Done: `collective qr`, `--expires-days`, `collective rotate` (stdlib QR encoder) |
| Public separability benchmark (synthetic traces, published AUCs per release) | Measure progress honestly | Done: `noisycompany benchmark`, release job summary, [BENCHMARK.md](BENCHMARK.md). Result: DNS noise still trivially separable by window features (AUC 0.98-1.00) |
| Real energy measurement (RAPL / smart plug) published in IMPACT.md | Replace estimates by measurements | Done: `noisycompany energy`; CPU time measured (17 ms/session), RAPL joules need a root run |
| Business profiles for more sectors + scenario files for SOC exercises | Detection engineering market | Done: logistics, education, manufacturing; `noisycompany scenario` with 3 scenarios |

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
