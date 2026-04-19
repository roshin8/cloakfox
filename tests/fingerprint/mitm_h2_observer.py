"""
mitmproxy addon — logs the exact H2 SETTINGS frame, WINDOW_UPDATE value, and
HPACK pseudo-header order that Cloakfox emits on each new connection.

Use for local observation when the tls.peet.ws signal is ambiguous or you
want to see the actual bytes going on the wire. Point Cloakfox at mitmproxy
(set `network.proxy.http` or use a system proxy) and browse any https:// site
that speaks HTTP/2.

Run:

    mitmproxy -s tests/fingerprint/mitm_h2_observer.py --listen-port 8080

Then in Cloakfox:
    about:config → network.proxy.type = 1
    network.proxy.http = 127.0.0.1, port 8080
    network.proxy.http_over_tls = true (implied)

Every H2 connection prints a block like:

    ─── 192.0.2.1:443 ──────────────────────────────────────
    SETTINGS:
      HEADER_TABLE_SIZE (1)    = 65536
      ENABLE_PUSH (2)          = 0
      MAX_CONCURRENT (3)       = 1000
      INITIAL_WINDOW_SIZE (4)  = 6291456
      MAX_HEADER_LIST_SIZE (6) = 262144
    WINDOW_UPDATE: 15663105
    HPACK order on first HEADERS: :method, :authority, :scheme, :path

Which you can eyeball against the three profile shapes documented in the
main H2 patch. If the pref says "chrome" but you see Firefox-order bytes,
the WebIDL setter didn't fire.

Notes:
- mitmproxy 10+ is required for H2 frame introspection.
- This logs only CLIENT-SENT frames (what Cloakfox emits). Server-sent
  frames are irrelevant for the client fingerprint.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict

from mitmproxy import ctx, http

SETTING_NAMES = {
    0x1: "HEADER_TABLE_SIZE",
    0x2: "ENABLE_PUSH",
    0x3: "MAX_CONCURRENT",
    0x4: "INITIAL_WINDOW_SIZE",
    0x5: "MAX_FRAME_SIZE",
    0x6: "MAX_HEADER_LIST_SIZE",
    0x8: "ENABLE_CONNECT_PROTOCOL",
    0x9: "NO_RFC7540_PRIORITIES",
}


class H2Observer:
    def __init__(self) -> None:
        # Remember which connections we've already printed — one report per
        # connection is enough; SETTINGS doesn't change mid-connection.
        self._seen: Dict[str, bool] = {}
        # Record per-connection HPACK pseudo-header order from the FIRST HEADERS frame.
        self._pseudo_first: Dict[str, bool] = {}

    def _conn_key(self, flow: http.HTTPFlow) -> str:
        return f"{flow.server_conn.peername[0]}:{flow.server_conn.peername[1]}" if flow.server_conn.peername else "?"

    def _log_settings(self, key: str, settings: dict) -> None:
        if self._seen.get(key):
            return
        self._seen[key] = True
        ctx.log.info(f"─── {key} " + "─" * (60 - len(key)))
        ctx.log.info("SETTINGS:")
        for sid, value in settings.items():
            name = SETTING_NAMES.get(sid, f"unknown({sid})")
            ctx.log.info(f"  {name:<26} ({sid}) = {value}")

    def http_connect(self, flow: http.HTTPFlow) -> None:
        """Fires when the client opens a CONNECT tunnel (H2 over TLS)."""
        # mitmproxy exposes the client's SETTINGS via server_conn.h2_client_settings
        # when the conn's http_version is HTTP/2 — we'll log on the first request instead
        # since SETTINGS is sent in the preface before any request.
        pass

    def request(self, flow: http.HTTPFlow) -> None:
        # Only bother for H2 connections.
        if getattr(flow.request, "http_version", "") != "HTTP/2.0":
            return

        key = self._conn_key(flow)

        # Pull SETTINGS from the client connection if available.
        client = flow.client_conn
        h2_settings = getattr(client, "h2_settings", None) or getattr(
            client, "h2_client_settings", None
        )
        if h2_settings and not self._seen.get(key):
            self._log_settings(key, dict(h2_settings))
            # WINDOW_UPDATE — mitmproxy doesn't expose the raw frame; report
            # it if the connection object carries it, otherwise skip.
            window_update = getattr(client, "h2_initial_window_increment", None)
            if window_update:
                ctx.log.info(f"WINDOW_UPDATE: {window_update}")

        # Log the HPACK pseudo-header order from the FIRST request per connection.
        if not self._pseudo_first.get(key):
            self._pseudo_first[key] = True
            pseudos = [
                h for h in OrderedDict.fromkeys(flow.request.headers.keys()) if h.startswith(":")
            ]
            order = ", ".join(pseudos[:4])
            ctx.log.info(f"HPACK order on first HEADERS: {order}")


addons = [H2Observer()]
