# Experimental network adapter verification

Work on `codex/firefox-157-port`, based on `845c12c0e4`. Native Firefox 157.0.1-beta.25 macOS arm64. Reference: actual installed Chrome 155.0.8059.40, captured by the existing local reference probe.

## Behavior

Settings → Persona & identity → Identity has a per-container **Match network profile to browser identity (experimental)** checkbox. It defaults off. Chrome/Chromium desktop major 155 selects one captured Gecko profile for TCP TLS, HTTP/2, QUIC TLS and HTTP/3; other versions/families retain native networking and show unsupported status. The master switch wins. Shared intent and capability descriptors are separate from the Gecko implementation so a future Chromium engine can register its own adapter. Changing UA does not switch engines.

The connection captures an atomic profile ID. Connection hashes, origin coalescing, TCP TLS provider/peer IDs and QUIC peer IDs partition profiles. TLS policy/security bits remain intact. Active connections retain their captured profile; same-profile connections may be reused if the choice returns to that profile. WebTransport retains its native profile because required negotiation capabilities are outside this adapter.

## Local runtime evidence

All requested origins are loopback fixtures in disposable profiles, with private fixture certificate authorities. No real Cloudflare, bank or assessment challenge is a verification target. Certificate verification remains enabled.

- TLS/HTTP2 identity probe: measured cipher/group/key-share ordering, SETTINGS, connection window and pseudo-header order match the captured Chrome reference; native and master-off remain unchanged. Untrusted and wrong-host certificates fail.
- QUIC identity probe: real TLS cipher/group/key-share fields, receive/stream limits and final HTTP/3 SETTINGS pass. Actual cache lookups with 0-RTT enabled use separate Chrome/native peer keys. This proves key isolation, not successful resumed/0-RTT payload exchanges. Exact-owner pooling, switch-back reuse and blocked/required-proxy refusal pass. WebTransport native TLS fallback is verified at handshake level; a complete WebTransport API exchange is not covered.
- Controls probe: same-origin connection reuse stays scoped to owner/profile, conservative requests remain native, TLS 1.2 and disabled-cipher policy win, blocked/required-proxy routes cannot fall back directly.
- Settings probe: actual production DOM handlers, identity/master changes, two open views, exact-container isolation and browser-restart persistence pass. DOM event activation is used because spoofed dimensions interfere with Selenium physical click geometry.
- Chrome-profile WebSocket probe: real WSS TLS cipher order, ws/wss echo, reconnect, proxy routing and refusal pass.
- Native regressions: stock Firefox TLS/HTTP2 and QUIC/HTTP3 parity, ws/wss routes, real HTTP3 controls, HTTPS DoH/DNS, TCP speculative/IPv6 controls and proxy policy pass.

RED→GREEN evidence includes baseline TLS/QUIC cipher mismatches, startup reconciliation, prototype adapter-name rejection, config observer behavior, unmeasured Chrome versions, HTTP2 socket-snapshot timing, QUIC unidirectional receive initialization, obsolete draft datagram SETTINGS and QUIC cache keys.

## Remaining acceptance

This is a partial implementation of the user's full network-matching request. ALPS, trust-anchor IDs, other TLS extensions/signatures, complete GREASE shape, QUIC extensions/packet behavior, comprehensive ECH/resumption/0-RTT, generation draining, retry/migration and QPACK-pressure acceptance remain open. WebTransport exposes native signals. Matching the measured fields does not make Gecko indistinguishable from Chrome. The UI discloses that limitation, and TODO.md retains the full-matching item unchecked.

Build succeeds. Patch replay: 111 patches, 256 targets, zero drift/offset/fuzz. Units: 231 JavaScript passed; 24 Python passed, 16 opt-in historical/live tests skipped (not claimed as current verification). Mounted package verification and whole-change review are pending at this checkpoint.
