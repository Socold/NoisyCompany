# Measuring how separable the noise is

`noisycompany study` answers one question: **could an observer that sees hostnames and
timing (ISP, resolver, Wi-Fi) filter NoisyCompany's traffic out of yours?**

## 1. Collect

1. `noisycompany features on labelled_log`, run for a few days. The noise is written to
   `~/.local/state/noisycompany/labelled.jsonl`.
2. Give a real trace from the same network and period:
   - Pi-hole: pass a copy of `/etc/pihole/pihole-FTL.db` directly (opened read-only);
   - AdGuard Home: `querylog.json` as is;
   - anything else: any CSV or JSONL with a time column (`ts`, `timestamp`, `time`, `date`) and a host
   column (`host`, `domain`, `name`, `query`, `target`) works.

The trace stays on your machine. Do not publish it: it is your real browsing.

## 2. Measure

```bash
noisycompany study --noise ~/.local/state/noisycompany/labelled.jsonl \
                   --human queries.csv --exclude-noise-hosts
```

`--exclude-noise-hosts` removes from the trace the lines that are the noise itself
(same second and host), since a DNS log of the network contains both.

## 3. Read

| ROC AUC | Meaning |
|---|---|
| ~0.5 | indistinguishable with these features |
| 0.6-0.75 | partly separable |
| 0.75-0.9 | largely separable |
| > 0.9 | trivially separable: an observer can drop the noise |

The output lists the most telling features (positive weight = looks like noise), for
example `unique_hosts` (a real page load resolves dozens of third-party hosts) or
`hour_sin/hour_cos` and `day_off` (activity at hours or on days you are never online).
Remedies: tune active hours, `weekly_rhythm` (hours and days), `third_party_bursts` and
`dns_coherence` (host diversity and revisits), `request_trees`, or the browser companion.

## Packets and TLS (`--pcap`)

```bash
sudo tcpdump -i eth0 -w capture.pcap 'tcp port 443'      # a few hours, while you browse
noisycompany study --noise ~/.local/state/noisycompany/labelled.jsonl --pcap capture.pcap
```

Flows to port 443 are labelled noise when their TLS server name (SNI) is a host the
daemon fetched within 5 s of the flow start; the rest is your traffic. Features: packet
counts, bytes and mean sizes both ways, duration, ClientHello length, cipher suites,
extensions, GREASE and ALPN `h2`. pcap and pcapng, Ethernet, VLAN, Linux cooked and raw IP.
Encrypted Client Hello hides the SNI: such flows are skipped.

Expected result: **trivially separable**. The daemon speaks TLS through Python's `ssl`
(checked: no GREASE, no ALPN, 35 suites), unlike any browser. A TLS-aware observer can
filter daemon web noise flow by flow. The browser companion does not have this limit: it
uses the browser's own TLS stack.

## Limits

One observer model per study, no cross-household view. NetFlow exports carry no
ClientHello: only the DNS study applies to them.
A high AUC is a real warning; a low AUC is not a proof of safety. Expect DNS-level noise
from the daemon to be largely separable from a real DNS log (no third-party bursts): its
value is in diluting the *interest categories* of hostnames, not in being invisible.

## Benchmark

Without a real trace, `noisycompany benchmark` runs the same study against a synthetic
household, offline. Results per release: [BENCHMARK.md](BENCHMARK.md).
