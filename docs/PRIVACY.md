# Data privacy

NoisyCompany is a privacy tool, so it must not become a privacy problem. This page lists
**everything it sends, stores and reads**. It is checked at each release (last review:
[SECURITY_AUDIT_2026-11.md](SECURITY_AUDIT_2026-11.md)).

## What leaves your machine

| Destination | When | What is sent | Personal data |
|---|---|---|---|
| Persona websites (Wikipedia, hobby sites...) | HTTP noise | GET request, one generic browser user agent, `Accept-Language` matching the persona, `DNT: 1`, `Sec-GPC: 1`. No cookie, no referrer, no form | Your public IP address (that is the point: it is diluted with decoys) |
| Your system DNS resolver | DNS noise | Hostnames of persona sites | Your IP, as for any lookup |
| DoH resolver (`doh_url`, Cloudflare by default) | Only if `doh_sink` is on | DNS queries of persona hostnames over HTTPS | Your IP. Choose the resolver your browser already uses |
| GitHub Container Registry | Only when you pull the image | Standard registry requests | As for any download |

Nothing else. There is no telemetry, analytics, update check or crash report, and no
account or server run by the project. The dashboard and metrics endpoints listen on
`127.0.0.1` only.

The Firefox companion sends the same kind of requests as the daemon:
- **light mode**: no cookie, redirects not followed;
- **tab mode** (Firefox): a hidden tab loads the page in a separate container. Trackers
  on that page see a decoy visit, and your cookies are not involved, unless you choose
  the default container (opt-in, with a warning): then the visit uses your cookies;
- **daemon link** (opt-in): one read-only request to `127.0.0.1` (the daemon's
  dashboard) per tick. Nothing leaves the machine.

## What is stored locally

In `~/.local/state/noisycompany/` (or `--state-dir`), directory `0700`, files `0600`:

| File | Content | Why |
|---|---|---|
| `salt` | Random 128-bit value | Makes your persona rotation unpredictable to others |
| `features.json` | On/off switches | Your choices |
| `stats.json` | Counters, active persona names | Dashboard, metrics |
| `health` | Last heartbeat time | Only with `appliance_packages` |
| `labelled.jsonl` (+ `.1`) | Each **noise** action: time, kind, target URL/host, bytes, persona | Only with `labelled_log`; never your own traffic; rotated at 10 MB |
| `collective.json` | Collective name, shared salt, persona names | Only after `collective join` |
| `packs/*.toml` | Installed persona packs | Only after `packs install` |

The companion stores its settings, a 20-entry visit log (persona, host, size) and a
salt in the extension's local storage. Nothing is synchronised.

## What is read locally

- `/proc/net/dev` (traffic counters) for netwatch. Only byte totals, no connection data.
- `nmcli` output (metered flag), only with `metered_guard`.
- **Privacy report** (`privacy_report`, opt-in): Firefox `prefs.js`, `user.js`,
  `extensions.json` and Chromium-family `Local State` / extension IDs, `resolvectl status`,
  `/proc/sys/net/ipv6/conf/all/use_tempaddr`. The output contains booleans and the names
  of known blockers only. No path, no history, no other extension name.
- **Energy** (`noisycompany energy`): `/sys/class/powercap/*/energy_uj` counters only.
- **Benchmark and scenarios**: fully offline, nothing read but the bundled data.
- **Study** (`noisycompany study`): the trace file you pass. It is processed in memory
  and not copied. Do not publish your trace.

## Sharing

- A **collective share code** contains a shared secret and persona names, nothing that
  identifies you. Anyone with the code can predict the collective's decoys, so share it
  only with members. A code cannot add new domains (reviewed personas only).
- **Bug reports**: do not attach `labelled.jsonl` or study traces. Use `--dry-run` logs.

## Your rights and the law

The project collects no personal data, so there is no controller and nothing to request.
On a network you do not own (employer, school), the generated traffic is attributable
to you: check the rules before running it.
