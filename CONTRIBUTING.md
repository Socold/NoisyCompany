# Contributing

- Keep the runtime **dependency-free** (Python standard library only).
- Every change that can increase traffic must update `NoisyCompany estimate` and docs/IMPACT.md.
- New personas: add a pack in `src/noisycompany/data/packs/<name>.toml` (see existing ones)
  and run `noisycompany packs check <file>`; CI runs it too. No sensitive categories,
  text-light pages, sites whose robots.txt allows crawling.
- Run `ruff check . && pytest -q` before opening a pull request.
- Never commit personal data, logs or `stats.json`.
