"""Polite, size-capped HTTP fetching and link extraction (stdlib only)."""

from __future__ import annotations

import gzip
import http.client
import ipaddress
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser

log = logging.getLogger(__name__)

# Approximate request + TLS handshake + headers overhead, in bytes.
REQUEST_OVERHEAD = 6_000
# Decompressed HTML is capped too: a 192 KB gzip body could otherwise inflate ~1000x.
MAX_DECODED_BYTES = 2_000_000
_PUBLIC_CACHE: dict[str, tuple[float, tuple[str, ...]]] = {}


def public_addresses(host: str, resolver=socket.getaddrinfo, ttl_s: float = 600,
                     port: int = 443) -> tuple[str, ...]:
    """Addresses of host if every one is globally routable, else ().

    Blocks loopback, RFC 1918, link-local, CGNAT, ULA... so that a compromised or
    rebinding persona domain cannot turn noise into requests against the LAN (router
    admin pages, NAS, Home Assistant) or the machine itself. The pinned connections
    below connect to one of these very addresses, so there is no second lookup.
    """
    host = host.strip("[]").lower()
    now = time.monotonic()
    cached = _PUBLIC_CACHE.get(host)
    if cached and now - cached[0] < ttl_s:
        return cached[1]
    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = resolver(host, port, proto=socket.IPPROTO_TCP)
        except (OSError, UnicodeError):
            return ()
        addrs = [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]
    ok = tuple(dict.fromkeys(str(a) for a in addrs)) if addrs and all(
        a.is_global for a in addrs) else ()
    if len(_PUBLIC_CACHE) > 4096:
        _PUBLIC_CACHE.clear()
    _PUBLIC_CACHE[host] = (now, ok)
    return ok


def is_public_host(host: str, resolver=socket.getaddrinfo, ttl_s: float = 600) -> bool:
    """True only if every address the host resolves to is globally routable."""
    return bool(public_addresses(host, resolver, ttl_s))


def _pinned_socket(host: str, port: int, timeout, source_address=None) -> socket.socket:
    """Connect to an address that passed the public check, never to a fresh lookup."""
    last: OSError = OSError(f"{host} does not resolve to public addresses only")
    for ip in public_addresses(host, port=port):
        try:
            return socket.create_connection((ip, port), timeout, source_address)
        except OSError as exc:
            last = exc
    raise last


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = _pinned_socket(self.host, self.port, self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        sock = _pinned_socket(self.host, self.port, self.timeout, self.source_address)
        # SNI and certificate checks still use the hostname, only the IP is pinned.
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):  # type: ignore[override]
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):  # type: ignore[override]
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context)


class _ScopedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to http(s), to a public host, within the persona scope."""

    def __init__(self, fetcher: Fetcher) -> None:
        super().__init__()
        self.fetcher = fetcher

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        if not self.fetcher.url_allowed(newurl):
            log.debug("redirect to %s refused", newurl)
            return None  # urllib then raises HTTPError(code): counted as a failed page
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "a":
            href = a.get("href")
            if href and not href.startswith("#"):
                self.links.append(href)
        elif tag == "link" and "stylesheet" in (a.get("rel") or "").lower() and a.get("href"):
            self.assets.append(a["href"] or "")
        elif tag == "script" and a.get("src"):
            self.assets.append(a["src"] or "")


def extract_assets(html: str, base_url: str) -> list[str]:
    """Same-origin stylesheet and script URLs of a page, in document order."""
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - truncated or broken HTML is expected
        log.debug("html parse error on %s", base_url)
    origin = urllib.parse.urlsplit(base_url)
    out: list[str] = []
    for raw in parser.assets:
        try:
            u = urllib.parse.urlsplit(urllib.parse.urljoin(base_url, raw.strip()))
        except ValueError:
            continue
        if (u.scheme, u.netloc) != (origin.scheme, origin.netloc):
            continue
        clean = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, u.query, ""))
        if clean not in out:
            out.append(clean)
    return out


def extract_links(html: str, base_url: str) -> list[str]:
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - truncated or broken HTML is expected
        log.debug("html parse error on %s", base_url)
    out: list[str] = []
    seen: set[str] = set()
    for raw in parser.links:
        try:
            absolute = urllib.parse.urljoin(base_url, raw.strip())
            parsed = urllib.parse.urlsplit(absolute)
        except ValueError:
            continue
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            continue
        clean = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def host_allowed(url: str, domains: list[str]) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def is_blocked(url: str, fragments: list[str]) -> bool:
    low = url.lower()
    return any(f in low for f in fragments)


@dataclass
class FetchResult:
    url: str
    status: int
    wire_bytes: int
    html: str = ""


@dataclass
class Fetcher:
    user_agent: str
    timeout_s: float
    max_response_bytes: int
    respect_robots: bool = True
    per_host_delay_s: float = 20.0
    max_assets_per_page: int = 3
    _robots: dict[str, urllib.robotparser.RobotFileParser | None] = field(default_factory=dict)
    _assets_seen: set[str] = field(default_factory=set)
    # Persona scope: redirects may only land on these domains (None = any public host).
    scope: list[str] | None = None
    accept_language: str = "en-US,en;q=0.7"
    _opener: urllib.request.OpenerDirector | None = None

    def url_allowed(self, url: str) -> bool:
        try:
            parts = urllib.parse.urlsplit(url)
        except ValueError:
            return False
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return False
        if self.scope is not None and not host_allowed(url, self.scope):
            return False
        return is_public_host(parts.hostname)

    def _open(self, req: urllib.request.Request):
        if self._opener is None:
            handlers: list[urllib.request.BaseHandler] = [_ScopedRedirects(self)]
            if not urllib.request.getproxies():  # behind a proxy, the proxy resolves
                handlers += [_PinnedHTTPHandler(), _PinnedHTTPSHandler()]
            self._opener = urllib.request.build_opener(*handlers)
        return self._opener.open(req, timeout=self.timeout_s)
    _last_hit: dict[str, float] = field(default_factory=dict)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Sec-GPC": "1",
        }

    def host_ready_in(self, url: str, now: float | None = None) -> float:
        host = urllib.parse.urlsplit(url).hostname or ""
        now = time.monotonic() if now is None else now
        last = self._last_hit.get(host)
        return 0.0 if last is None else max(0.0, last + self.per_host_delay_s - now)

    def allowed_by_robots(self, url: str) -> tuple[bool, int]:
        """Return (allowed, bytes spent fetching robots.txt)."""
        if not self.respect_robots:
            return True, 0
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        spent = 0
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            res = self._get(origin + "/robots.txt", decode=True, cap=64_000)
            spent = res.wire_bytes if res else REQUEST_OVERHEAD
            if res and res.status < 400:
                rp.parse(res.html.splitlines())
                self._robots[origin] = rp
            else:
                self._robots[origin] = None  # no robots.txt: allowed
        rp = self._robots[origin]
        allowed = True if rp is None else rp.can_fetch(self.user_agent, url)
        return allowed, spent

    def _get(self, url: str, decode: bool, cap: int) -> FetchResult | None:
        if not self.url_allowed(url):
            log.debug("refused %s (non-public or out of scope)", url)
            return None
        req = urllib.request.Request(url, headers=self._headers(), method="GET")  # noqa: S310
        host = urllib.parse.urlsplit(url).hostname or ""
        self._last_hit[host] = time.monotonic()
        try:
            with self._open(req) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if "html" not in ctype and "text/plain" not in ctype:
                    return FetchResult(url, resp.status, REQUEST_OVERHEAD)
                raw = resp.read(cap)  # stop reading at the cap, then close the socket
                status = resp.status
                encoding = resp.headers.get("Content-Encoding", "")
                charset = resp.headers.get_content_charset() or "utf-8"
        except urllib.error.HTTPError as exc:
            return FetchResult(url, exc.code, REQUEST_OVERHEAD)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log.debug("fetch %s failed: %s", url, exc)
            return None
        wire = REQUEST_OVERHEAD + len(raw)
        text = ""
        if decode:
            text = _decode(raw, encoding, charset)
        return FetchResult(url, status, wire, text)

    @property
    def asset_cap(self) -> int:
        return self.max_response_bytes // 2

    def subresources(self, html: str, page_url: str) -> list[str]:
        """Assets not fetched yet (a browser cache would hold them). Robots checked by caller."""
        out = []
        for asset in extract_assets(html, page_url):
            if len(out) >= self.max_assets_per_page:
                break
            if asset in self._assets_seen:
                continue
            if len(self._assets_seen) > 2000:
                self._assets_seen.clear()
            self._assets_seen.add(asset)
            out.append(asset)
        return out

    def fetch_asset(self, url: str) -> int:
        """Download up to asset_cap bytes and discard them. Returns wire bytes."""
        if not self.url_allowed(url):
            return 0
        headers = self._headers() | {"Accept": "*/*"}
        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        try:
            with self._open(req) as resp:
                return REQUEST_OVERHEAD + len(resp.read(self.asset_cap))
        except (urllib.error.URLError, OSError, ValueError):
            return REQUEST_OVERHEAD

    def fetch(self, url: str) -> FetchResult | None:
        return self._get(url, decode=True, cap=self.max_response_bytes)


def _decode(raw: bytes, encoding: str, charset: str) -> str:
    try:
        if "gzip" in encoding:
            # Truncated stream: decompress what we have, never more than the cap.
            raw = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, MAX_DECODED_BYTES)
        elif "deflate" in encoding:
            raw = zlib.decompressobj().decompress(raw, MAX_DECODED_BYTES)
    except (zlib.error, gzip.BadGzipFile):
        return ""
    try:
        return raw[:MAX_DECODED_BYTES].decode(charset, errors="replace")
    except LookupError:  # unknown charset announced by the server
        return raw[:MAX_DECODED_BYTES].decode("utf-8", errors="replace")
