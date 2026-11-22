"""Minimal M3U / M3U8 IPTV playlist parser (stdlib only).

Handles the common extended-M3U format:

    #EXTM3U
    #EXTINF:-1 tvg-name="..." tvg-logo="..." group-title="...",Display Name
    https://example.com/stream.m3u8

Unknown attributes are ignored; a malformed entry is skipped rather than
raising, so a single bad line in a long playlist does not break the app.
"""

from __future__ import annotations

import re

_ATTR_RE = re.compile(r'([a-zA-Z0-9\-]+)="([^"]*)"')


def parse(text: str) -> list[dict]:
    channels: list[dict] = []
    pending: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            pending = _parse_extinf(line)
            continue
        if line.startswith("#"):
            continue
        if pending is None:
            continue
        if not (line.startswith("http://") or line.startswith("https://")):
            pending = None
            continue
        pending["url"] = line
        channels.append(pending)
        pending = None
    return channels


def _parse_extinf(line: str) -> dict:
    body = line[len("#EXTINF:"):]
    name = ""
    if "," in body:
        body, name = body.split(",", 1)
        name = name.strip()
    attrs = {m.group(1).lower(): m.group(2) for m in _ATTR_RE.finditer(body)}
    return {
        "name": name or attrs.get("tvg-name", ""),
        "logo": attrs.get("tvg-logo", ""),
        "group": attrs.get("group-title", ""),
    }
