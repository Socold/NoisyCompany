# Changelog

## Unreleased (3.3)

- `real_third_parties`: replays, DNS only, the hosts a real browser contacted when
  opening each persona site (recorded by headless Chromium, trackers removed), in the
  recorded order and spacing. Snapshot `data/third_parties.json`, refreshed by the
  monthly `third-parties` workflow (`tools/third_party_snapshot.py`).

## 2.2.0 (2026-11-08)

- `browser_dns`: per-host lookup cache (2-10 min TTL) and an HTTPS record (type 65)
  query next to A/AAAA, as current browsers do. Benchmark 0.95 -> 0.94.
- `household_masking`: a virtual household of 2-5 members drawn from the local salt
  (own hobbies, own hours, sometimes online together), redrawn every 30-90 days, with a
  floor of activity during active hours so the head-count and empty-home periods do
  not show. Overrides `interleave_with_user`, which would reveal presence.
- Docker image: `/state` belongs to the unprivileged user, so a new named volume works
  on first start (it failed with "Permission denied").

## 2.1.0 (2026-11-08)

First release on PyPI (`pip install noisycompany`). Bundles 2.1, 2.2, 2.3, 2.4 and 3.x.

Carried-over items (3.1):

- Per-persona rhythm: optional `rhythm = ["sat-sun 07-12"]` peak windows, followed when
  `weekly_rhythm` is on (3x inside, 0.4x outside); validated in config and packs.
- `page_load_bursts`: 5-25 hosts within about a second per page, embedded hosts first,
  then hosts the persona already read; never invented names.
- `interleave_with_user`: sessions start mostly while the local traffic counter shows
  you online. Benchmark: 0.97 -> 0.95 AUC; see docs/BENCHMARK.md for what it cannot show.
- Companion popup accessibility: the switch is named, help texts are linked, the usage
  line is a status region, visible focus, warning colour readable in dark mode.
- French CLI messages and help when `LANG` (or `NOISYCOMPANY_LANG`) is `fr`.
- CI builds the OpenWrt packages with the official SDK; artifact `openwrt-packages`.
- Home Assistant AppArmor profile, draft and parsed in CI (not active yet).
- `noisycompany study --pcap`: TLS flow study (sizes, timing, ClientHello shape).

Research and collective:

- Collective share codes as QR codes (terminal or SVG), expiry dates, `collective rotate`
  for a new shared salt. Expired codes cannot be joined; unknown fields are rejected.
- `noisycompany benchmark`: the real engine on a simulated clock and a fake network,
  scored against a synthetic household; published in each release summary and in
  docs/BENCHMARK.md.
- `noisycompany energy`: measured CPU time and RAPL energy per session.
- Business profiles logistics, education, manufacturing; `noisycompany scenario` makes
  labelled benign traffic for SOC tests offline, with no-beaconing and cap checks.

Integrations:

- Pi-hole / AdGuard Home deployment (`deploy/pihole/`) with the study on the FTL database.
- App templates for Umbrel, CasaOS, TrueNAS SCALE and Unraid (`deploy/apps/`).
- OpenWrt package with UCI config and LuCI page (`deploy/openwrt/package/`).
- Grafana dashboard for the Prometheus metrics (`deploy/grafana/`).
- Dashboard in French and accessibility fixes (focus kept on refresh, live regions,
  skip link, inline errors, reduced motion). The dashboard now accepts query strings.

Browser companion:

- Chromium port (Chrome, Brave, Edge), light mode only; `npm run build` makes both
  packages.
- Persona languages (en, fr, de, es, it), opt-in link to the daemon's
  `browser_companion` switch, tab mode in the default container behind a warning.
- Release job to sign the Firefox build on addons.mozilla.org (off until configured).

Realism, guided by the separability study (all new switches off by default):

- German, Spanish and Italian locale packs, with matching `Accept-Language`.
- `dns_coherence`: DNS noise follows the pages read and the links seen.
- `weekly_rhythm`: evening peaks, later weekend and holiday mornings, quieter summer.
- `third_party_bursts`: DNS lookups of a page's embedded third-party hosts, trackers
  skipped, no download.
- Study reads Pi-hole `pihole-FTL.db` and AdGuard Home `querylog.json` directly, and
  uses a weekday/holiday feature.

Hardening from the November 2026 audit:

- Connections go to the address that passed the public-IP check (no DNS rebinding
  window between check and connect).
- Seeded fuzz tests of the link parser, body decoder and share-code decoder; optional
  atheris harness in `fuzz/`.
- Home Assistant add-on runs the daemon as uid 10001; state moves to `/data/state`.
- Release images get a Sigstore-signed provenance attestation; PyPI trusted publishing
  workflow (off until configured).

## 2.0.1

Security and data-privacy audit fixes ([report](docs/SECURITY_AUDIT_2026-11.md)):

- Redirects and URLs must stay in the persona's domains and resolve to public IPs only
  (no LAN, loopback or metadata address): SSRF and DNS rebinding.
- Decompressed HTML capped at 2 MB; unknown charsets no longer stop the daemon.
- Companion no longer follows redirects.
- umask 077 and state directory 0700.
- `doh_url` must be https.
- Labelled log rotated at 10 MB.
- Dashboard rejects negative `Content-Length`.
- `Accept-Language` follows the persona's locale.
- CI actions pinned by commit SHA.
- `collective create` caps `active_count` to the persona count.
- New docs: PRIVACY, SECURITY_AUDIT_2026-11, ARCHITECTURE. Roadmap: next evolutions.

## 2.0.0 (2026-11-01)

First stable release of the rewrite. Every roadmap item is implemented, each behind an
on/off switch that is off by default. Multi-arch image: `ghcr.io/socold/noisycompany:v2.0.0`.

## 2.0.0a5 (pre-release)

- `appliance_packages`: Home Assistant add-on, docker-compose, Raspberry Pi installer,
  OpenWrt service, GHCR multi-arch release workflow, `noisycompany health` + HEALTHCHECK.
- `collective_noise`: share codes with digest, reviewed personas only, shared rotation.
- `separability_study`: `noisycompany study`, ROC AUC with k-fold CV, telling features.
- Every roadmap item is now implemented.

## 2.0.0a4 (pre-release)

- `browser_companion`: Firefox WebExtension (MV3) in `companion/`, personas and manifest
  generated by `noisycompany companion export`, node tests and Mozilla linter in CI.
- `business_profiles`: office, dev_team and retail profiles, profile in the labelled log.
- `request_trees`: same-origin CSS/JS once per URL, robots.txt checked, budgeted.

## 2.0.0a3 (pre-release)

- `privacy_report`: `noisycompany privacy` + dashboard card, local read-only checks and score.
- `persona_marketplace`: `noisycompany packs`, 4 reviewed packs, validator run in CI.

## 2.0.0a2 (pre-release)

- Feature switches for every roadmap item (`noisycompany features`, dashboard buttons).
- New: persona drift, French persona pack, metered guard, DoH sink, Prometheus metrics,
  local dashboard, labelled ground-truth log.
- DNS noise no longer invents subdomains (NXDOMAIN was a giveaway).

## 2.0.0a1 (pre-release)

Complete rewrite of the NoisyCompany idea:
personas, DNS + polite HTTP noise, hard budget with daily pacing, netwatch back-off,
active hours, impact estimator, dry-run, hardened systemd unit, non-root Docker image,
zero runtime dependency.
