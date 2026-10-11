# Optional Chrome network identity

User requirement, 2026-10-11: when choosing a Chrome identity, an optional
Settings toggle must select Chrome HTTP/2, TLS and QUIC together. The previous
HTTP/2-only behavior and the newer always-Firefox automatic behavior do not
meet this requirement.

## Required behavior

- Settings → Identity exposes one toggle, **Match network profile to browser
  identity**, saved for the selected container. Default off preserves Firefox
  networking. Switching the master protection off restores Firefox networking.
- With the toggle on and a supported Chrome identity selected, newly established
  connections use the same versioned Chrome profile for HTTP/2, TCP TLS,
  QUIC TLS, QUIC transport parameters and HTTP/3 SETTINGS/QPACK limits.
- Unsupported families/versions must have an explicit status; they must not
  silently use a partly matching Chrome profile. No claim to change Gecko's
  page APIs or rendering engine.
- The connection captures the exact container's profile at creation. Pooling,
  coalescing, resumption tickets and 0-RTT must not mix profile generations.
  Existing connections drain on a profile change; no UI promise that reloading
  alone changes an already pooled connection.
- Certificate/hostname verification, TLS version restrictions, enterprise
  cipher policy, actual ECH, proxy routing, container isolation and DNS policy
  continue to work. Never advertise TLS/QUIC capabilities without implementing
  their negotiated behavior.

## Measured implementation gap

The reference probe runs installed Chrome against fresh loopback TLS/H2 and
QUIC/H3 servers. It does not test a public challenge or assessment. The measured
reference is Chrome 155.0.8059.40 on macOS arm64; other majors/platforms require
their own measurements. See
[reference artifact](../../firefox-157-port/chrome-network-reference.json).

- Existing Chrome H2 code advertises MAX_CONCURRENT_STREAMS=1000; the captured
  Chrome H2 SETTINGS omit that field.
- Existing Chrome H3 SETTINGS include ENABLE_CONNECT=1 and put blocked streams
  before max header size. Chrome captures use QPACK_MAX_TABLE_CAPACITY=65536, then max
  header size 262144, blocked streams 100 and H3_DATAGRAM=1. The real decoder
  must support everything it advertises.
- TLS differs in cipher order, groups, key-share count, signatures, extension
  sets and extension randomization. Chrome captures include application
  settings (17613) and trust-anchor IDs (51764); the existing NSS/PSM paths do
  not implement their Chrome protocol behavior. Adding dummy extensions or
  changing UA/appVersion would not meet this spec.
- QUIC differs in flow-control limits, stream limits, UDP/datagram limits,
  connection-ID shape, version information and extension parameters. Copying
  HTTP/3 SETTINGS alone leaves these differences intact.

The reference parser strips GREASE and payloads, so it proves only these
structural differences. It cannot certify complete Chrome equivalence.

## Acceptance before enabling the toggle

Compare repeated fresh and resumed local connections to the supported real
Chrome release, retaining GREASE placement/shape and decoded extension payload
semantics while excluding random secret material. Cover TLS 1.2 and 1.3,
HelloRetryRequest, ECH, ALPS, QUIC versions/retry/migration, HTTP/3 fallback,
QPACK pressure, proxy failures, WebSockets, and update/download connections.
Prove invalid certificates fail, policy restrictions win, and two containers
plus profile switches cannot share pools/tickets across profiles. Test the
actual Settings toggle and packaged binary, including default-off migration.

## Future Chromium engine boundary

User requirement, 2026-10-11: preserve room for a Chromium engine. Browser-family intent belongs to a shared parent-process selector. A Gecko adapter owns its native profile IDs and NSS/neqo metadata; a future Chromium adapter must register capabilities and consume the same intent through its actual stack. Changing UA does not select an engine. Unknown/uninstalled adapters report unavailable.

## Current work

An experimental Gecko adapter and a container-scoped Settings toggle are being implemented. The first phase shapes measured Chrome 155 cipher/group/key-share ordering, H2 settings and pseudo-header order, QUIC flow-control/stream limits and H3 settings. The default remains native Firefox.

This phase does **not meet full Chrome equivalence or the complete acceptance criteria above**. ALPS, trust-anchor IDs, full GREASE shape, QUIC extensions/packet behavior, comprehensive ECH/resumption/0-RTT and profile-generation draining remain open. Settings must disclose these gaps. Build/runtime/package verification is pending; the existing DMG is unchanged until a new verified package is recorded.
