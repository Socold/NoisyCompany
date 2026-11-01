# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.0.x | yes |
| < 2.0 (pre-releases, original noisy) | no |

## Reporting

Please report vulnerabilities privately through GitHub's
"Report a vulnerability" button (Security tab of this repository). Do not open a public
issue. We aim to answer within 7 days.

In scope:
- anything that makes NoisyCompany fetch what it should not: LAN or loopback addresses,
  out-of-scope redirects, blocked URLs, ads, payloads beyond the caps;
- exceeding its budget;
- leaking local data in requests or share codes;
- running code from fetched content;
- driving the localhost dashboard from a web page;
- a companion behaviour beyond its declared permissions.

NoisyCompany never executes fetched content.

Past audits: [docs/SECURITY_AUDIT_2026-11.md](docs/SECURITY_AUDIT_2026-11.md).
Data inventory: [docs/PRIVACY.md](docs/PRIVACY.md).
