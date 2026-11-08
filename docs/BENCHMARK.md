# Separability benchmark

`noisycompany benchmark` runs the real engine for simulated days, offline, against a
synthetic household DNS trace, and scores each configuration with the separability study
(ROC AUC: 0.5 = indistinguishable, 1.0 = trivially filtered). It is reproducible (fixed
seed) and runs in each release workflow, whose summary shows the table.

## Latest results

| Configuration (v2.2.0, 14 simulated days, seed 7) | ROC AUC | Noise events | Most telling features |
|---|---|---|---|
| baseline (eco) | 1.00 | 2768 | unique_hosts, www_ratio, events |
| + weekly_rhythm | 1.00 | 2443 | unique_hosts, www_ratio, events |
| + dns_coherence | 1.00 | 2657 | unique_hosts, unique_ratio, events |
| + third_party_bursts | 0.98 | 3916 | www_ratio, unique_hosts, events |
| all 2.2 realism switches | 0.98 | 3534 | unique_hosts, events, gap_std |
| + page_load_bursts | 0.95 | 3887 | unique_hosts, events, gap_std |
| + interleave_with_user | 0.94 | 4169 | unique_hosts, events, www_ratio |
| + browser_dns | 0.94 | 3752 | events, unique_hosts, unique_ratio |
| + household_masking | 0.94 | 3659 | events, unique_hosts, www_ratio |
| + real_third_parties | 0.97 | 3870 | www_ratio, unique_hosts, gap_std |

`real_third_parties` scores worse here (0.96-0.97, runs vary by a hundredth) and that says more about the synthetic
household than about the noise: its page loads use made-up `cdn.` / `static.` hosts
without `www.`, while the recorded loads contain real names such as `www.google.com` or
`www.gstatic.com`, so `www_ratio` separates them. Only `noisycompany study` on a real
trace can tell whether real page loads blend better; the switch stays off by default.

`household_masking` is not meant to lower this score: it changes what an observer can
infer about the household (head-count, empty-home periods), which this benchmark does
not measure. The HTTPS-record queries of `browser_dns` are not modelled either (the
synthetic trace has no query types).

Since 3.1 the synthetic pages embed 5-25 third-party hosts, like the household's, instead
of 4; the first rows moved by a few hundredths for that reason only.

## Reading

- **The DNS-level noise is still easy to filter for this observer.** Real page loads
  resolve 5-25 hosts within a second; NoisyCompany resolves a few, spread out. A
  window-based classifier sees it at once (`unique_hosts`, `events`).
- `third_party_bursts` is the only switch that moves the score today (0.98), because it
  is the only one that adds hosts per page. Up to 4 per page is far from 5-25: raising
  `third_party_max` trades bandwidth-free DNS lookups for realism.
- `weekly_rhythm` and `dns_coherence` change *when* and *which* hosts, which this
  synthetic household cannot reward: its sessions are already in the same hours, and
  its revisits come from favourite sites, not from noise.
- Consequence for users: against a resolver that groups queries into windows, the noise
  mostly costs it a filter. It still adds decoy interests to per-domain profiles (which
  sites were looked up at all), which is what DNS-based ad profiling uses. See
  [THREAT_MODEL.md](THREAT_MODEL.md).

## Limits

The household is a model (Zipf favourites, evening and weekend peaks, device chatter),
the network is fake, and the observer is one logistic regression on DNS windows. Track
the trend between releases; measure your own case with `noisycompany study`.

- `page_load_bursts` (3.1) gives the best score so far, 0.95: page-sized bursts make
  noise windows look more like page loads, but window volume still differs.
- `interleave_with_user` (3.1) does not move this score, and that is expected: the
  study labels each window as noise *or* household, so it cannot reward noise that
  hides inside the user's own windows. Its value is against an observer that only sees
  the mixed stream (the real case), where off-hours noise is the first thing to filter.

## Next steps suggested by the benchmark

- A mixed-stream observer (windows labelled by majority) to measure interleaving.
- Session volume closer to the household's (fewer, larger sessions at the same budget).
