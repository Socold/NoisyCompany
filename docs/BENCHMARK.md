# Separability benchmark

`noisycompany benchmark` runs the real engine for simulated days, offline, against a
synthetic household DNS trace, and scores each configuration with the separability study
(ROC AUC: 0.5 = indistinguishable, 1.0 = trivially filtered). It is reproducible (fixed
seed) and runs in each release workflow, whose summary shows the table.

## Latest results

| Configuration (v2.0.1, 14 simulated days, seed 7) | ROC AUC | Noise events | Most telling features |
|---|---|---|---|
| baseline (eco) | 1.00 | 2751 | unique_hosts, www_ratio, events |
| + weekly_rhythm | 1.00 | 2436 | unique_hosts, www_ratio, events |
| + dns_coherence | 1.00 | 2672 | unique_hosts, unique_ratio, events |
| + third_party_bursts | 0.98 | 4164 | unique_hosts, www_ratio, events |
| all 2.2 realism switches | 0.98 | 3692 | unique_hosts, events, gap_std |


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

## Next steps suggested by the benchmark

- Bursts closer to real page loads (more hosts per page, sub-second spacing).
- Sessions that interleave with the household's own browsing instead of standing alone.
