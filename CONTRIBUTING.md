# Contributing

- Keep the runtime **dependency-free** (Python standard library only).
- Every change that can increase traffic must update `NoisyCompany estimate` and docs/IMPACT.md.
- New personas: add a pack in `src/noisycompany/data/packs/<name>.toml` (see existing ones)
  and run `noisycompany packs check <file>`; CI runs it too. No sensitive categories,
  text-light pages, sites whose robots.txt allows crawling.
- Run `ruff check . && pytest -q` before opening a pull request.
- Never commit personal data, logs, `stats.json`, `labelled.jsonl` or study traces.
- Any new network path must go through `Fetcher.url_allowed` (scheme, persona scope,
  public IP) and be budgeted; any new local file goes in the state directory (0700).
- Any new data sent or stored must be added to `docs/PRIVACY.md`.
- New features get a switch in `features.py`, off by default, and a line in
  `docs/ROADMAP.md`.
- CI actions are pinned by commit SHA (Dependabot updates them).
