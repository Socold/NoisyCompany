# Contributing

- Keep the runtime **dependency-free** (Python standard library only).
- Every change that can increase traffic must update `NoisyCompany estimate` and docs/IMPACT.md.
- New personas: use the issue template; no sensitive categories, text-light pages,
  sites whose robots.txt allows crawling.
- Run `ruff check . && pytest -q` before opening a pull request.
- Never commit personal data, logs or `stats.json`.
