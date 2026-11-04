# Changelog

## 2.0.0a3 (unreleased)

- `privacy_report`: `noisycompany privacy` + dashboard card, local read-only checks and score.
- `persona_marketplace`: `noisycompany packs`, 4 reviewed packs, validator run in CI.

## 2.0.0a2 (unreleased)

- Feature switches for every roadmap item (`noisycompany features`, dashboard buttons).
- New: persona drift, French persona pack, metered guard, DoH sink, Prometheus metrics,
  local dashboard, labelled ground-truth log.
- DNS noise no longer invents subdomains (NXDOMAIN was a giveaway).

## 2.0.0a1 (unreleased)

Complete rewrite of the NoisyCompany idea:
personas, DNS + polite HTTP noise, hard budget with daily pacing, netwatch back-off,
active hours, impact estimator, dry-run, hardened systemd unit, non-root Docker image,
zero runtime dependency.
