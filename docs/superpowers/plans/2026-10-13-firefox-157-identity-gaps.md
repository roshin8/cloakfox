# Firefox 157 identity-gap port

> Execution: implement in this isolated checkout, then run independent code review.

**Goal:** Port the verified Firefox 146 identity/privacy fixes to Firefox 157.0.1 and verify their behavior on a freshly built 157 executable.

**Architecture:** Preserve the existing 157 native architecture, schemeful-site identity, network adapters and permission handling. Adapt only missing behavior; do not replace newer 157 files wholesale with 146 versions. Keep durable native modifications in ordered patches and additions in their source modules.

**Constraints:** Preserve existing checkouts and installed profiles. No MAIN-world inject scripts. Keep native master-off behavior, explicit container ownership, browser-internal principal exclusions and real media consent. No publishing or installation requested.

## Review focus

- Cross-container and worker startup/update identity; process-wide native caches remain native.
- Synchronous blank frames and opaque/system principal scope.
- Native font load statuses, URL fallback and disabled-mode recovery.
- Valid WebGL readback, padding and compute opt-out; deterministic canvas channels.
- TURN proxy route changes, DIRECT failover lists, negotiation and ICE restart.

## Execution

- [x] Prepare pristine 157 source and apply its existing stack; record baseline tests and version.
- [x] Compare every 146 gap fix with its 157 implementation. Reuse equivalent 157 protection and port missing graphics/fonts, realm/locale, HTTP/WebSocket/media and TURN behavior.
- [x] Bring forward the corresponding regression probes and settings tests, preserving newer 157 tests and pref names through explicit adaptation.
- [x] Reconcile additions and ordered native patches; replay against clean source with zero rejected hunks and verify source parity.
- [x] Build 157 on macOS arm64, fixing compile incompatibilities in their owning patches. Do not edit source during builds.
- [x] Run Node and Python tests plus disposable-profile local runtime probes for all ported features and relevant 157 regressions.
- [x] Run independent code review, fix material findings and rerun affected checks.
- [x] Record verified executable version, exact test counts and remaining limitations.

Verification: [identity-gap-verification.md](../../firefox-157-port/identity-gap-verification.md).
