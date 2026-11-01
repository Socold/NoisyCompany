# Security and data-privacy audit, November 2026 (v2.0.0)

Scope: the whole repository at v2.0.0. That covers the daemon (`src/noisycompany/`),
the localhost dashboard and metrics servers, the Firefox companion (`companion/`),
the appliance packaging (`deploy/`, Dockerfile, compose), the CI/CD workflows and the
git history.

Method:
- manual review of every input that crosses a trust boundary (network responses,
  redirects, share codes, packs, config files, local HTTP requests, extension messages);
- `gitleaks` on the full history and a grep for personal data;
- one regression test per fix (`tests/test_security.py`).

Fixes ship in 2.0.1.

## Summary

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | High | HTTP redirects were followed to any host, including LAN and loopback addresses (SSRF from a compromised persona site) | Fixed |
| 2 | High | Persona domains were not checked to resolve to public IPs (DNS rebinding toward the LAN) | Fixed |
| 3 | Medium | gzip/deflate bodies were decompressed without limit (a 192 KB "bomb" inflates to hundreds of MB) | Fixed |
| 4 | Medium | Companion `fetch` followed redirects: blind requests to LAN addresses possible | Fixed |
| 5 | Medium | State files (salt, collective secret, labelled log, stats) were created with the default umask (world-readable on most systems) | Fixed |
| 6 | Low | Unknown charset announced by a server raised an uncaught `LookupError` and stopped the daemon | Fixed |
| 7 | Low | Dashboard POST with a negative `Content-Length` read the socket to EOF (local slow request) | Fixed |
| 8 | Low | `doh_url` accepted `http://`, sending DNS noise in clear text | Fixed |
| 9 | Low | Labelled log grew without bound | Fixed (10 MB rotation) |
| 10 | Low | CI/CD actions referenced by mutable tags | Fixed (pinned to commit SHA, Dependabot keeps them current) |
| 11 | Privacy | French personas were fetched with an English `Accept-Language` header: an easy tell, and a fingerprint mismatch | Fixed (header follows the persona's locale) |
| 12 | Info | `collective create` refused a short persona list instead of capping `active_count` | Fixed |
| 13 | Accepted | Home Assistant add-on runs as root inside its container (Supervisor owns `/data`) | Documented; container isolation, no capability requested |
| 14 | Accepted | The daemon's TLS fingerprint differs from a browser's | By design, see THREAT_MODEL; companion covers it |

No secret and no personal data were found in the git history (gitleaks: no leaks; only
GitHub `noreply` author addresses).

## Details

### 1-2. SSRF / DNS rebinding (fixed)

Before, `urllib.request.urlopen` followed any redirect, and links were filtered only by
hostname. A compromised persona site, or one whose DNS was rebound, could make every
NoisyCompany instance request `http://192.168.1.1/...` or `http://127.0.0.1:8123/...`.
Typical targets are router admin pages, NAS or Home Assistant, with the user's IP as the
source.

Now `Fetcher.url_allowed()` is enforced for the first request, every redirect hop
(`_ScopedRedirects`), subresources and robots.txt. It requires:
- an `http`/`https` scheme;
- a host inside the persona's domains;
- every resolved address globally routable (`ipaddress.is_global`).

That excludes loopback, RFC 1918, link-local and cloud metadata `169.254.169.254`,
CGNAT, ULA and unspecified addresses. Answers are cached for 10 minutes.

Residual: a TOCTOU window between the check and urllib's own resolution. It is
acceptable here (the noise has no credentials and reads public pages only), and noted in
the roadmap (connect to the checked address).

### 3. Decompression bomb (fixed)

The decompressed output is capped at 2 MB (`MAX_DECODED_BYTES`). Share codes were
already capped (64 KB, `eof` and `unconsumed_tail` checked).

### 4. Companion redirects (fixed)

`fetch(..., {redirect: "manual"})`: a redirect ends the visit. Cross-origin reads were
already blocked by the host permissions, but the request itself was sent.

### 5. File permissions (fixed)

The CLI sets `umask 077` and the engine sets the state directory to `0700`. The salt and
`collective.json` were already `0600`.

## Data privacy review

See [PRIVACY.md](PRIVACY.md) for the full inventory. Results:

- **No telemetry**, no update check, no crash report, no third-party service contacted
  except the persona sites, the system DNS resolver and the configured DoH resolver
  when `doh_sink` is on (Cloudflare by default).
- **Requests carry no personal data**: no cookie (daemon has no cookie jar, companion uses
  `credentials: "omit"`), no referrer, one generic user agent, `DNT` and `Sec-GPC` set.
- **Local data** is limited to what is needed:
  - salt;
  - switches;
  - stats;
  - an opt-in labelled log of the noise only, never the user's own traffic.
- **The privacy report reads browser profiles** (prefs, extension lists) on the local
  disk. It outputs booleans and extension names only (tested: no path, no history), and
  is opt-in.
- **The study** reads a trace the user exports. It stays local, and the docs warn
  against publishing it.
- **Collective share codes** contain a shared secret (salt) and persona names, no
  identity. They can only reference reviewed personas, so a member cannot add a domain
  and learn other members' IP addresses.
- **Logs**: URLs only at DEBUG level.

## Recommendations kept for the roadmap

- Connect to the vetted IP (remove the TOCTOU window), for example with a custom
  `HTTPSConnection`.
- Sign release images with cosign (keyless, GitHub OIDC) and publish the verification
  command.
- Run the Home Assistant add-on as a non-root user once Supervisor mapping allows it.
- Fuzz the HTML/link parser and share-code decoder (atheris) in CI.
