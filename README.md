# NoisyCompany

**A lightweight, bandwidth-aware network noise generator with coherent decoy personas.**

noisycompany runs quietly in the background and adds plausible, low-volume browsing and DNS
activity to your connection, so that what a network observer (ISP, public Wi-Fi operator,
DNS resolver, router vendor) sees about you is diluted by interests that are not yours.

It is a ground-up rewrite of the idea behind [1tayH/noisy](https://github.com/1tayH/noisy)
(GPL-3.0), designed around three constraints the original did not have:

1. **Be honest about what noise can and cannot do** (see [threat model](docs/THREAT_MODEL.md)).
2. **Be featherweight**: a few MB per day by default, hard caps, pauses when you use your
   bandwidth, sleeps at night (see [impact](docs/IMPACT.md)).
3. **Be hard to filter out**: stable personas instead of uniform randomness, one consistent
   user agent, human-like pacing.

> NoisyCompany is a complement, not a replacement, for blocking. To stop targeted advertising,
> first use a content blocker (uBlock Origin), encrypted DNS and a browser that resists
> fingerprinting. NoisyCompany then lowers the value of what still leaks at network level.
> Read [what NoisyCompany does not do](docs/THREAT_MODEL.md#what-noisy-does-not-protect-against).

## Features

- **Personas**: 10 built-in harmless interest profiles (gardening, astronomy, chess...),
  3 active at a time, rotated every 10 days from a local secret salt.
- **DNS noise** through your system resolver (~300 bytes per lookup).
- **Polite HTTP browsing**: robots.txt honoured, per-host delay, responses truncated at
  192 KB, text/HTML only (no images, video, scripts), no ad, login or payment URL ever.
- **Hard budget**: daily MB cap, actions per hour cap, budget spread over the day.
- **Netwatch** (Linux): backs off while your own traffic exceeds 400 kbit/s.
- **Human schedule**: active hours, exponential gaps between sessions, reading time.
- **`noisycompany estimate`**: data, energy and CO2e per month before you run anything.
- **Zero runtime dependency**: Python standard library only, ~1000 lines with comments, easy to audit.
- **On/off switches for every roadmap item** (`noisycompany features`, or buttons in the
  local dashboard): persona drift, French persona pack, metered-link guard, DNS over
  HTTPS, Prometheus metrics, labelled ground-truth log for SOC testing, household privacy
  report, reviewed persona packs, business traffic profiles for SOC labs, realistic
  request trees, page-load bursts, browser-like DNS, household masking. Full list in
  [docs/ROADMAP.md](docs/ROADMAP.md).
- **Household masking** (`household_masking`): the noise comes from a virtual household
  of 2-5 members (own hobbies and hours, sometimes online together), redrawn every 30-90
  days, so it does not tell how many people live here or when the home is empty.
- **Browser-like DNS** (`browser_dns`): per-host cache and HTTPS-record queries, as
  current browsers do.
- **Appliances**: Home Assistant add-on, docker-compose, Raspberry Pi installer, OpenWrt
  service, multi-arch image, `noisycompany health`.
- **Collective noise**: households share a short code and rotate the same decoys.
- **`noisycompany study`**: measures how separable the noise is from your real traffic
  (ROC AUC), see [docs/STUDY.md](docs/STUDY.md).
- **Firefox companion** ([companion/](companion/README.md)): the same rare decoy visits
  made by your real browser, so they share its network fingerprint. Off by default.
- **`noisycompany privacy`**: local score of what really protects you (blocker, encrypted
  DNS, fingerprinting protection...), with advice. Nothing is sent.
- `--dry-run` mode, hardened systemd user unit, non-root Docker image.

## Quick start

```bash
pipx install noisycompany   # or: pip install noisycompany
noisycompany estimate                # what will it cost?
noisycompany run --dry-run --once    # what would it do? (no network)
noisycompany run                     # go
```

Default (`balanced`) estimate:

```
Data/day (expected)      : ~15 MB (hard cap 15 MB)
Average rate when active : ~2.2 kbit/s
Equivalent HD video/day  : ~18 s
Network energy/month     : 2.3 to 27 Wh
```

Presets: `eco` (~2 MB/day, DNS-heavy), `balanced` (~15 MB/day), `max` (~60 MB/day).

```bash
noisycompany config --print-default > noisycompany.toml   # edit, then
noisycompany run -c noisycompany.toml
```

### Switches and dashboard

```bash
noisycompany features                   # every roadmap item, with its state
noisycompany features on dashboard      # then open http://127.0.0.1:9788
noisycompany features on locale_packs   # add persona packs in your language (fr, de, es, it)
noisycompany privacy                    # local privacy score and advice
noisycompany packs install photography  # reviewed persona pack, then:
noisycompany features on persona_marketplace
```

### As a service

```bash
cp deploy/systemd/noisycompany.service ~/.config/systemd/user/
systemctl --user enable --now noisycompany
```

### Docker, Raspberry Pi, Home Assistant, OpenWrt

```bash
docker compose up -d                                   # docker-compose.yml
bash deploy/raspberrypi/install.sh                      # read it first; eco preset
```

Home Assistant: add this repository as an add-on repository, install *NoisyCompany*
(`deploy/homeassistant/`). Also:

| Where | Files |
|---|---|
| Pi-hole / AdGuard Home box (noise + study) | [deploy/pihole/](deploy/pihole/README.md) |
| Umbrel, CasaOS, TrueNAS SCALE, Unraid | [deploy/apps/](deploy/apps/README.md) |
| OpenWrt package + LuCI page | [deploy/openwrt/](deploy/openwrt/README.md) |
| Grafana (Prometheus metrics) | [deploy/grafana/](deploy/grafana/README.md) |

The dashboard is in English and French (browser language, or `?lang=fr`).

`--network host` lets netwatch see your real traffic; without it, only the budget applies.

## Documentation

| Document | Content |
|---|---|
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Who sees what, what noise changes, and what it does not |
| [docs/STATE_OF_THE_ART.md](docs/STATE_OF_THE_ART.md) | Existing tools and research, and why this design |
| [docs/IMPACT.md](docs/IMPACT.md) | Bandwidth, browsing and ecological impact |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Every feature with its on/off switch, available and planned |
| [docs/OPPORTUNITIES.md](docs/OPPORTUNITIES.md) | Use cases, product ideas |
| [docs/STUDY.md](docs/STUDY.md) | Measuring how separable the noise is |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Everything NoisyCompany sends, stores and reads |
| [docs/SECURITY_AUDIT_2026-11.md](docs/SECURITY_AUDIT_2026-11.md) | Security and data-privacy audit of v2.0.0 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, data flow, design rules |
| [companion/README.md](companion/README.md) | Firefox companion |
| [docs/fr/README.md](docs/fr/README.md) | Résumé en français |

## Commands

| Command | Purpose |
|---|---|
| `noisycompany run [--dry-run] [--once]` | Generate noise |
| `noisycompany estimate [-p preset]` | Data, energy, CO2e before running |
| `noisycompany features [on\|off <id>]` | List or flip the switches |
| `noisycompany privacy [--json]` | Local privacy report and score |
| `noisycompany packs [list\|install\|remove\|check]` | Reviewed persona packs |
| `noisycompany collective [show\|create\|join\|leave\|qr\|rotate]` | Shared decoys across households, QR codes, expiry, new salt |
| `noisycompany study --noise ... --human ...` | Separability (ROC AUC) |
| `noisycompany benchmark [--days 14]` | Offline separability benchmark ([results](docs/BENCHMARK.md)) |
| `noisycompany energy [--sessions 20]` | Measured CPU time and RAPL energy per session |
| `noisycompany scenario [list\|run <name>]` | Labelled benign traffic for SOC tests, offline |
| `noisycompany health` | Liveness for supervisors / Docker |
| `noisycompany companion export [--check]` | Regenerate the Firefox companion files |
| `noisycompany personas`, `noisycompany config` | Inspect personas and effective config |

## Security and privacy

No telemetry, no account, no server. Every URL and redirect must stay on the persona's
domains and resolve to public IPs only, so a hostile site cannot aim your traffic at your
LAN. State files are private (0700/0600). Details: [PRIVACY.md](docs/PRIVACY.md),
[audit](docs/SECURITY_AUDIT_2026-11.md), [SECURITY.md](SECURITY.md).

Images from 2.1 on carry a signed build provenance. Check it before running:

```bash
gh attestation verify oci://ghcr.io/socold/noisycompany:v2.2.0 -R Socold/NoisyCompany
```

## Responsible use

noisycompany only reads public pages, at human pace, and honours robots.txt. It never clicks
ads (that would be click fraud in many jurisdictions), never submits forms, never logs in.
Do not raise the limits to levels that put load on small sites. On a shared or employer
network, the generated traffic is visible and attributable to you: check the rules first.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). Inspired by 1tayH/noisy (GPL-3.0); no code
was reused.
