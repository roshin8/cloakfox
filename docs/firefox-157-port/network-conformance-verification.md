# Network protocol conformance continuation

Branch `codex/firefox-157-port`, continuation baseline `b93259177a`. Engine:
Firefox157.0.1-beta.25, macOSarm64. Reference: installed Chrome155.0.8059.40.
The toggle remains experimental, per-container and default-off. Only measured
Chrome/Chromium desktop major155 is supported. The existing independent adapter
contract remains ready for a future Chromium implementation.

## Implemented and demonstrated

- TCP/QUIC handshake signature order follows one shared Chrome list after NSS
  policy/version filtering. Peer handshake signatures cannot select removed
  schemes; chain-validation policy is unchanged. Native mode retains P-521.
- TCP GREASE cipher/group/version/share/extension placement, QUIC presentation,
  certificate-compression offer (Brotli only), extension omissions and ECH
  GREASE algorithm/length/placement now have detailed wire checks. HRR sends
  only the requested P-256 keyshare and preserves stable GREASE/ECH placement.
- QUIC uses genuine empty source CIDs, eight-byte initial destination CIDs,
  QUICv1 support/preference and1250-byte Initial datagrams. Real receive limits,
  stream/QPACK decoder capacities and65536-byte datagram capability match the
  reference; reserved transport parameters have genuine randomized lengths/order.
- TCP h2 and QUIC h3 negotiate ALPS with authenticated client
  EncryptedExtensions, owned application settings and existing protocol consumers.
  H2 HEADER_TABLE_SIZE=0 affects the first HPACK block. H3 QPACK capacity64
  is observed before ordinary server SETTINGS, proving actual consumption.
- ALPS state is owned by the isolated NSS session/token. Native tokens without
  ALPS retain their existing encoding. TCP ALPS resumption succeeds; actual
  QUIC Retry, resumed handshakes and accepted0RTT exchanges succeed. Accepted
  0RTT uses cached ordinary H3 settings, which can supersede earlier ALPS.
- A fresh ECH exchange uses genuine DNS HTTPS records through verified local
  DoH. BoringSSL decrypts the ClientHello and both peers report accepted ECH
  in native and Chrome-profile mode; this is separate from ECH GREASE.
- Adversarial unadvertised zlib certificate compression, unadvertised P-521
  handshake signatures, malformed H2/H3 ALPS and oversized H2 initial windows
  are rejected. Native/server behavior and certificate-chain policy remain
  separate from the optional client presentation profile.

## Evidence and repair

The fixtures use disposable profiles and loopback-only origins. Product probes
keep certificate verification enabled and import a private fixture CA only into
those profiles. Chrome reference probes use a temporary leaf-SPKI pin. Existing
profiles, system trust and installed applications were not changed.

BoringSSL fixture source reference: official commit
`5b83e5d1abf0ae0033ae52ab579d906b67633b2c`.
The H3 fixture adds authenticated client EE and verifies Finished over the
updated transcript; successful response alone is insufficient proof of ALPS.

RED→GREEN evidence: baseline signature ordering, HRR extra GREASE keyshare,
QUIC Initial/CID lengths, idle QUIC ticket publication, absent TCP/H3 ALPS,
unoffered certificate decompression, datagram32768 versus actual reference65536,
transient early_data ECH anchor, unoffered handshake signature acceptance and
oversized H2 ALPS windows. False failures caused by the H2 priority prefix,
reused Alt-Svc fixture routes and random native ECH AEAD choice were repaired in
the harness, without weakening protocol checks to accommodate product behavior.

One fresh reviewer identified the signature mismatch and two minor validation
issues; all were repaired. Follow-up found no further Critical or Important issue
in those repairs. See [review](network-adapter-review.md).

Latest native build: success, zero compiler warnings. Units:234 Node passed;
32 Python passed,16 historical/opt-in tests skipped. Native CI unittest discovery:
13 passed. Patch replay:112 patches/280 pristine targets, no offset/fuzz/drift.
Mounted-package runtime acceptance is recorded in [checks](network-conformance-checks.txt).
The mounted XUL UUID matches the native build, its bytes match the package stage,
and seven resource files match tracked sources. See
[artifact inventory](network-conformance-packaged-check.json).

## Full matching remains open

This continuation does not certify full Chrome equivalence. Remaining work:
trust-anchor IDs tied to actual trusted roots, NSS-policy signature differences
(for example disabled ML-DSA), HTTP/2 priority behavior, ECH retry/QUIC acceptance,
advanced QUIC loss/congestion/migration and real H3 ORIGIN support, QPACK pressure
and further fallback scenarios. ACCEPT_CH framing is validated but unsolicited
client hints are not enabled. WebTransport retains native networking.

Matching captured presentation fields and real protocol paths does not make
NSS/neqo behave identically to Chromium's entire network stack. Gecko page/rendering
APIs also remain Gecko. The full-matching TODO remains unchecked; Chromium engine
integration remains future work. The new artifact is a development/ad-hoc signed
DMG, not a notarized release.

Implementation and evidence commit `cf2c058d4d` is pushed to
`origin/codex/firefox-157-port`. DMG SHA-256:
`1024cfb8e4b3b4e947b9e1266cab977d12f9623c6de53280fd6a35946234def2`.
Full matching is still unfinished; this commit records verified progress.
