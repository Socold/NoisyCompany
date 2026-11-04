# NoisyCompany add-on

Adds rare, plausible DNS and web activity from your Home Assistant host so that what your
ISP or DNS resolver sees about the household is diluted with harmless decoy interests.

- Eco preset by default: about 2-3 MB per day, nothing at night.
- Pauses while the network is busy (host network mode).
- Health is reported to the Supervisor (`noisycompany health`).

Options: `preset` (eco, balanced, max), `daily_mb` hard cap, `active_hours`,
`locale_packs` (French personas), `doh_sink`, `privacy_report`.

It complements, and does not replace, a content blocker and encrypted DNS. Read the
threat model: https://github.com/Socold/NoisyCompany/blob/main/docs/THREAT_MODEL.md
