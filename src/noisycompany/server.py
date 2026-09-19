"""Localhost-only HTTP endpoints: Prometheus metrics and the dashboard with on/off buttons.

Hardening, because a local web UI is reachable by any web page the user opens:
- binds 127.0.0.1 only;
- rejects any Host header that is not 127.0.0.1/localhost on our port (DNS rebinding);
- state-changing requests need a per-process random token and a same-origin Origin;
- strict Content-Security-Policy, no inline script, no third-party resource.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any, Protocol

from noisycompany.features import NotAvailable, UnknownFeature

log = logging.getLogger(__name__)

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class StatusSource(Protocol):
    def status(self) -> dict[str, Any]: ...
    features: Any


def render_metrics(status: dict[str, Any]) -> str:
    s = status["stats"]
    lines = []

    def metric(name: str, kind: str, help_: str, value: float, labels: str = "") -> None:
        lines.append(f"# HELP noisycompany_{name} {help_}")
        lines.append(f"# TYPE noisycompany_{name} {kind}")
        lines.append(f"noisycompany_{name}{labels} {value}")

    metric("sessions_total", "counter", "Noise sessions run.", s["sessions"])
    lines.append("# HELP noisycompany_dns_lookups_total DNS noise lookups.")
    lines.append("# TYPE noisycompany_dns_lookups_total counter")
    lines.append(f'noisycompany_dns_lookups_total{{result="ok"}} {s["dns_ok"]}')
    lines.append(f'noisycompany_dns_lookups_total{{result="fail"}} {s["dns_fail"]}')
    lines.append("# HELP noisycompany_pages_total Pages fetched.")
    lines.append("# TYPE noisycompany_pages_total counter")
    lines.append(f'noisycompany_pages_total{{result="ok"}} {s["pages_ok"]}')
    lines.append(f'noisycompany_pages_total{{result="fail"}} {s["pages_fail"]}')
    lines.append(f'noisycompany_pages_total{{result="robots_denied"}} {s["robots_denied"]}')
    metric("bytes_total", "counter", "Bytes transferred by noise since start.", s["bytes"])
    metric("bytes_today", "gauge", "Bytes transferred today.", status["bytes_today"])
    metric("daily_cap_bytes", "gauge", "Effective daily byte cap.", status["daily_cap_bytes"])
    metric("paused_busy_total", "counter", "Back-offs due to user traffic.", s["paused_busy"])
    metric("paused_budget_total", "counter", "Waits due to budget.", s["paused_budget"])
    metric("metered", "gauge", "1 if the connection is metered.", int(status["metered"]))
    return "\n".join(lines) + "\n"


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    server_version = "noisycompany"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
        log.debug("http: " + fmt, *args)

    # ------------------------------------------------------------ helpers
    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        return host in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        port = self.server.server_address[1]
        return origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: Any) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    # ------------------------------------------------------------ routes
    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._send(421, b"misdirected", "text/plain")
            return
        src = self.server.source
        if self.server.mode == "metrics":
            if self.path == "/metrics":
                self._send(200, render_metrics(src.status()).encode(),
                           "text/plain; version=0.0.4")
            else:
                self._send(404, b"not found", "text/plain")
            return
        if self.path == "/":
            html = _asset("dashboard.html").replace("__TOKEN__", self.server.token)
            self._send(200, html.encode(), "text/html; charset=utf-8")
        elif self.path == "/app.js":
            self._send(200, _asset("dashboard.js").encode(), "text/javascript")
        elif self.path == "/app.css":
            self._send(200, _asset("dashboard.css").encode(), "text/css")
        elif self.path == "/api/status":
            self._json(200, src.status() | {"features": src.features.snapshot()})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.server.mode != "dashboard" or not self._host_ok() or not self._origin_ok():
            self._send(403, b"forbidden", "text/plain")
            return
        if not secrets.compare_digest(self.headers.get("X-NC-Token", ""), self.server.token):
            self._send(403, b"bad token", "text/plain")
            return
        prefix = "/api/features/"
        if not self.path.startswith(prefix):
            self._send(404, b"not found", "text/plain")
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 1024)
            body = json.loads(self.rfile.read(length) or b"{}")
            on = body["on"]
            if not isinstance(on, bool):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            self._json(400, {"error": "expected {\"on\": true|false}"})
            return
        fid = self.path[len(prefix):]
        try:
            self.server.source.features.set(fid, on)
        except UnknownFeature:
            self._json(404, {"error": "unknown feature"})
            return
        except NotAvailable as exc:
            self._json(409, {"error": str(exc)})
            return
        log.info("feature %s switched %s from dashboard", fid, "on" if on else "off")
        self._json(200, {"id": fid, "enabled": on})


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, source: StatusSource, mode: str) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.source, self.mode = source, mode
        self.token = secrets.token_urlsafe(24)


def _asset(name: str) -> str:
    return resources.files("noisycompany.data").joinpath(name).read_text("utf-8")


class LocalServer:
    """Start/stop a localhost server in a daemon thread."""

    def __init__(self, port: int, source: StatusSource, mode: str) -> None:
        self.port, self.source, self.mode = port, source, mode
        self._server: _Server | None = None

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def address(self) -> tuple[str, int] | None:
        return self._server.server_address[:2] if self._server else None  # type: ignore[return-value]

    def start(self) -> None:
        if self._server:
            return
        try:
            self._server = _Server(self.port, self.source, self.mode)
        except OSError as exc:
            log.warning("%s server on 127.0.0.1:%d failed: %s", self.mode, self.port, exc)
            return
        threading.Thread(target=self._server.serve_forever, name=self.mode, daemon=True).start()
        log.info("%s on http://127.0.0.1:%d", self.mode, self._server.server_address[1])

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def sync(self, wanted: bool) -> None:
        if wanted:
            self.start()
        else:
            self.stop()
