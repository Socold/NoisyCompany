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
| `locale_packs` | 2.1 | Adds personas in your language (`fr` pack included, `locale_share` = 60 % of sessions) | none |
| `metered_guard` | 2.1 | NetworkManager reports a metered link: daily cap drops to the eco budget (3 MB) | saves data |
| `doh_sink` | 2.2 | DNS noise sent over DNS-over-HTTPS (RFC 8484) to `doh_url`, the resolver your browser uses | ~5 KB per lookup instead of ~300 B |
| `metrics` | 2.2 | Prometheus text on http://127.0.0.1:9789/metrics | none |
| `dashboard` | 2.2 | Local page: budget, KPIs, active personas, on/off buttons. Localhost only, anti DNS rebinding, CSRF token, strict CSP | none |
| `labelled_log` | 2.2 | JSONL ground truth of every action (`label: benign-noise`) for SOC / IDS / NDR testing | disk only |
| `privacy_report` | 2.3 | `noisycompany privacy` and a dashboard card: content blocker, encrypted DNS (browser DoH or systemd-resolved DoT), fingerprinting protection, GPC, IPv6 temporary addresses, noise running, noise DNS coherent with browser DNS. Score out of 100, advice for each gap. Read-only, local, no path or browsing data in the output | none |
| `persona_marketplace` | 2.3 | `noisycompany packs [list\|install\|remove\|check]`: reviewed packs shipped in `data/packs/` (photography, board games, knitting, aquariophilie FR), installed by copy, re-validated at load (a tampered pack is ignored). CI rejects packs with sensitive topics, non-HTTPS seeds, seeds outside their domains, login/ads URLs | none |

## Planned

| Switch | Milestone | Plan |
|---|---|---|
| `browser_companion` | 2.3 | WebExtension (Firefox first): rare persona visits inside the real browser, in a dedicated container, no ads, no clicks, same budget rules. The only way to act on browser-level ad profiling |
| `business_profiles` | 2.4 | Persona packs per business profile (office, dev team, retail, hospital admin) for SOC labs, with labelled output |
| `appliance_packages` | 2.4 | Raspberry Pi image, OpenWrt package, Home Assistant add-on, Pi-hole / AdGuard Home companion, Umbrel / CasaOS / TrueNAS apps |
| `request_trees` | 3.0 | Fetch a page's same-origin CSS/JS once (cached) so request trees look less bot-like; doubles bandwidth, hence opt-in |
| `collective_noise` | 3.0 | Households share persona sets (signed, peer-to-peer or static files) so decoy profiles are indistinguishable across users; no central server |
| `separability_study` | research | Capture + classifier kit to measure how well an observer can filter noise out; results published |

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
