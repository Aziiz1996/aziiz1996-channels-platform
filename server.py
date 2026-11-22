"""Local HTTP server for the TV channels desktop app.

Reads an M3U playlist once at startup, exposes the parsed channel list
at ``/api/channels`` and serves the static UI from ``static/``, then
opens the default browser at the local address.

Usage:
    python server.py --playlist sample.m3u
    python server.py --playlist https://example.com/list.m3u

All stdlib on the server side. The frontend loads hls.js from a CDN to
play HLS streams in the browser.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from m3u import parse

STATIC_DIR = (Path(__file__).resolve().parent / "static").resolve()
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def load_playlist(source: str) -> list[dict]:
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "channels-platform/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            text = resp.read().decode("utf-8", errors="replace")
    else:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    return parse(text)


def make_handler(channels: list[dict]):
    payload = json.dumps(channels, ensure_ascii=False).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/api/channels":
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", payload)
                return
            if path in ("", "/"):
                path = "/index.html"
            target = (STATIC_DIR / path.lstrip("/")).resolve()
            try:
                target.relative_to(STATIC_DIR)
            except ValueError:
                self._send(HTTPStatus.FORBIDDEN, "text/plain; charset=utf-8", b"forbidden")
                return
            if not target.is_file():
                self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found")
                return
            ctype = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self._send(HTTPStatus.OK, ctype, target.read_bytes())

        def log_message(self, fmt, *args):
            return

        def _send(self, status, ctype, body):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def pick_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Local TV channels player")
    ap.add_argument("--playlist", required=True, help="Path or URL to an M3U playlist")
    ap.add_argument("--port", type=int, default=0, help="Local port (0 = auto)")
    ap.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    args = ap.parse_args(argv)

    try:
        channels = load_playlist(args.playlist)
    except Exception as exc:
        print(f"failed to load playlist: {exc}", file=sys.stderr)
        return 2

    if not channels:
        print("playlist contains no channels", file=sys.stderr)
        return 2

    port = args.port or pick_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(channels))
    url = f"http://127.0.0.1:{port}/"
    print(f"serving {len(channels)} channels on {url}")

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
