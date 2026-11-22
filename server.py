"""Local HTTP server for the TV channels desktop app.

Reads an optional M3U playlist at startup, exposes the parsed channel
list at ``/api/channels``, serves the static UI from ``static/`` and
opens the default browser at the local address. A new playlist can
also be uploaded at runtime via ``POST /api/channels``.

Usage:
    python server.py                        # start empty, upload from UI
    python server.py --playlist sample.m3u  # preload a local file
    python server.py --playlist https://example.com/list.m3u

Stdlib only on the server side; the frontend loads hls.js from a CDN.
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
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # playlist uploads are capped at 10 MB
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Store:
    """Thread-safe current channel list, shared by every request handler."""

    def __init__(self, channels: list[dict] | None = None):
        self._lock = threading.Lock()
        self._channels = list(channels or [])

    def get(self) -> list[dict]:
        with self._lock:
            return list(self._channels)

    def set(self, channels: list[dict]) -> None:
        with self._lock:
            self._channels = list(channels)


def fetch_playlist(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "channels-platform/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return resp.read(MAX_UPLOAD_BYTES + 1).decode("utf-8", errors="replace")


def load_playlist(source: str) -> list[dict]:
    if source.startswith("http://") or source.startswith("https://"):
        text = fetch_playlist(source)
    else:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    return parse(text)


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/api/channels":
                payload = json.dumps(store.get(), ensure_ascii=False).encode("utf-8")
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

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/channels":
                self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found")
                return

            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "empty or oversized body"})
                return

            try:
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return

            text = data.get("text") if isinstance(data, dict) else None
            url = data.get("url") if isinstance(data, dict) else None

            if isinstance(url, str) and url and not isinstance(text, str):
                if not (url.startswith("http://") or url.startswith("https://")):
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "url must be http(s)"})
                    return
                try:
                    text = fetch_playlist(url)
                except Exception as exc:
                    self._json(HTTPStatus.BAD_GATEWAY, {"error": f"fetch failed: {exc}"})
                    return

            if not isinstance(text, str) or not text.strip():
                self._json(HTTPStatus.BAD_REQUEST, {"error": "text or url required"})
                return

            channels = parse(text)
            if not channels:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "no channels found in playlist"})
                return

            store.set(channels)
            self._json(HTTPStatus.OK, {"count": len(channels)})

        def log_message(self, fmt, *args):
            return

        def _json(self, status, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

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
    ap.add_argument("--playlist", help="Path or URL to an M3U playlist (optional; can also be uploaded from the UI)")
    ap.add_argument("--port", type=int, default=0, help="Local port (0 = auto)")
    ap.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    args = ap.parse_args(argv)

    channels: list[dict] = []
    if args.playlist:
        try:
            channels = load_playlist(args.playlist)
        except Exception as exc:
            print(f"failed to load playlist: {exc}", file=sys.stderr)
            return 2
        if not channels:
            print("playlist contains no channels", file=sys.stderr)
            return 2

    store = Store(channels)
    port = args.port or pick_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
    url = f"http://127.0.0.1:{port}/"
    if channels:
        print(f"serving {len(channels)} channels on {url}")
    else:
        print(f"serving on {url} (upload a playlist from the UI)")

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
