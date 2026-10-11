# Firefox 157 privacy follow-ups — 2026-10-11

Implemented on `codex/firefox-157-port` after pushed baseline `0030d79a81`.
The original checkout's remaining audit docs were committed/pushed first at
`ffd1cdf1f3`. Other historical worktrees, profiles and installed apps were preserved.

## Behavior

- Native Performance clocks/timeline entries now share exact-owner, site-derived
  session presentation keys, including dedicated/shared/service workers. The
  actor retains scheduling jitter and no longer wraps performance.now. Explicit
  author marks/measures are unchanged; public lists sort exposed timestamps.
  Each Performance global keeps one mode: reload pages/restart workers after
  timing-option or master-switch changes. Firefox precision reduction remains.
- Media enumeration keeps native permission filtering and real capture backing;
  configurable caps limit existing devices instead of inventing devices. Granted
  labels and capture-track labels are generic, including strict/empty enumeration.
  Native origin/container device-ID anonymization and rotating group IDs remain.
  Settings exposes enable/disable plus microphone/camera/speaker limits 0–64.
- HDR masking reports standard content video-dynamic-range while protected.
  Master/option-off, compatibility and live geometry site exceptions restore
  native capability. Privileged UI/compositor/capture are unchanged.
- Automatic H2/H3 configuration follows the actual Firefox engine regardless of
  UA text, including startup migration. Local wire measurements already match
  stock Firefox, so no NSS/cipher/TLS security changes were justified. Explicit
  experimental raw profile prefs remain separate from automatic behavior.

## Verification

- Native macOS arm64 build passed (`privacy-final-build.log`). All **110 patches**
  replay on **243 pristine targets** without offset, fuzz or native source drift
  (`privacy-replay.json`, `privacy-patch-replay.log`).
- Node: **220 passed**, no failures/skips (`privacy-node.log`). Python: **19 passed,
  16 skipped** (`privacy-pytest.log`); skipped cases are existing opt-in probes
  requiring additional binary/public-fixture setup, not the local runtime suite.
- **8 development-runtime probes passed** (`privacy-final-runtime.json`): the
  eight advertised timing types/observers, zero/opaque resource fields, new 157
  response phase getters, explicit marks, mixed-coordinate ordering, delayed
  getter/clock toggle controls, all worker types, media permissions/constraints,
  strict track labels, actual ownership/ID isolation, live Settings, forced HDR
  CSS/matchMedia and exceptions, generation checkbox, WebGL/audio and site isolation.
- **6 network probes passed** (`privacy-final-network.json`): actual repeatable
  TLS ClientHello, H2 SETTINGS/window updates/pseudo-header ordering, TLS 1.3,
  untrusted and wrong-host certificate rejection; QUIC parameters/H3 SETTINGS;
  ws/wss echo/upgrades/reconnect, live proxy and refused routes; UDP route sinks;
  DoH A/AAAA, strict failures and proxy DNS; speculative/IPv6 transport controls.
  QUIC TLS extension order remains randomized; compare extension sets while
  retaining raw order evidence. Randoms/keys/tickets/GREASE are not fixed identities.
- One fresh read-only whole-change review found four Important timing/UI issues
  and two Minor report/doc issues. Accepted and fixed with RED→GREEN evidence;
  no deferred Minor findings (`privacy-review.md`). Final green runtime checks
  cover the corrections; no second reviewer was dispatched.
- **11 mounted-DMG probes passed** (`privacy-packaged-runtime.json`,
  `privacy-packaged-network.json`). Packaged XUL hash equals the packaging stage;
  its native UUID matches the development library. Six modified packaged
  JS/HTML resources exactly match canonical sources. Stock crash resources and
  development-helper removal remain verified (`privacy-packaged-check.json`).

## Artifact and limits

`cloakfox-157.0.1-beta.25.en-US.mac.dmg`, macOS arm64, 122,612,817 bytes.
SHA256: `70c67d3f2e9619aa3c55bfe73e717256055235788ed9423fb17edb90c1a1ad7f`.

This is a development package; release signing/notarization remains pending.
Physical camera/microphone delivery, physical HDR playback and Windows/Linux
runtime remain separate acceptance. Resource timing retains its product default
of disabled; these probes explicitly enable its opt-in API for coverage. Timing
presentation is not a claim to remove every CPU-performance signal. No public
challenge or assessment was used, no user's browsing profile was changed, and
SharedArrayBuffer mitigation remains off. TLS validation/security policy remains
intact. Test mount detached after verification.

Source input hashes: `final-input-hashes.json`; current bundle metadata:
`artifacts.json`. Prior reports retain their historical package hashes.
