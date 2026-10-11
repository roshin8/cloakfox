# Timing, media, HDR and network privacy follow-ups

User authorized implementation and testing without a plan-review pause. Baseline
0030d79a81 is pushed on codex/firefox-157-port; the original checkout's remaining
audit documents were committed and pushed at ffd1cdf1f3.

## Boundaries

Use native Gecko protections and privileged actors. Preserve real capture,
permission gating, author-supplied timing values, TLS certificate checks,
TLS 1.3 and Firefox's supported cipher policy. Use disposable profiles and local
fixtures. Do not change installed applications or the user's browsing profile.
SharedArrayBuffer mitigation remains off. Network normalization follows the
actual Firefox engine; changing a UA does not change its TLS implementation.

## Work and acceptance

- [x] Timing: port the existing native Performance Timeline work to 157,
  including worker ownership, while resolving keys from exact owner overlays
  and site partitions. Retire the actor's separate performance.now clock.
  Test observers, resource/navigation phases, explicit marks/measures, repeated
  reads, monotonicity, worker fetch, master-off and option-off controls.
- [x] Media: replace synthetic-device substitution with a real-device exposure
  cap. Resolve config from the owner principal, obey permissions, normalize
  granted labels, and keep native origin/container device-ID anonymization and
  raw backing devices. Test missing/false config, counts, permissions, device
  IDs, constraints, frame/container ownership and capture using the local fake
  hardware fixture. Physical hardware delivery remains a separate acceptance.
- [x] HDR: mask content video-dynamic-range as standard while privacy applies;
  preserve privileged UI and compatibility/site geometry exceptions. Test a
  forced-HDR positive control, master-off, compatibility and per-container
  configurations, plus CSS/matchMedia consistency.
- [x] Network: capture local TLS ClientHello, H2 settings/header ordering and
  QUIC parameters/H3 SETTINGS, compared to installed stock Firefox 157.0.1.
  Correct demonstrated differences from Firefox's engine identity and preserve
  proxy/DNS route enforcement. Add local WebSocket routing/refusal/reconnect
  coverage and certificate rejection controls. Do not weaken TLS or add
  cross-engine transport imitation.
- [x] Build, run unit/native/runtime regressions, replay the complete patch
  stack without fuzz/offset, perform one fresh final review, package and test
  the DMG, record remaining platform/hardware limits, commit and push.

## Execution record

Ruling: retain the existing high-precision timing option's presentation semantics;
it adds deterministic presentation after native precision reduction, rather than
claiming to remove every CPU-performance signal. Coverage must be consistent.

Ruling: preserve other historical worktrees; their source changes are already
incorporated into the 157 baseline where applicable. Do not publish disposable
profiles or unrelated in-progress experiments.

Review focus: default-container exact ownership, worker thread safety, permissions
and real capture, cached timing values across option changes, TLS security and
actual wire evidence rather than preference-only assertions.

Ruling: capture timing presentation mode at Performance-global construction;
reload pages/restart workers to apply timing/master option changes. Mixing modes
within one timeline can invert lazy phase fields or move now() backwards.

Ruling: keep native device-ID persistence with permission and native per-window
group-ID rotation. Stable reload tests compare device IDs, not complete device
objects that deliberately contain rotating group IDs.

Ruling: stock Firefox randomizes QUIC TLS extension order; preserve that privacy
behavior. Compare extension sets plus ordered transport parameters/H3 SETTINGS,
and retain actual extension orders in the report.

Ruling: Firefox uses CONNECT for ws and wss through an HTTP proxy; adapt the
local fixture expectation to its actual supported routing.

Ruling: wire evidence showed stock structural parity, so no NSS/TLS security or
cipher change was justified. Fix the demonstrated UA-derived automatic H2
profile mismatch and preserve explicit experimental raw prefs.

Fresh review: four Important defects accepted and fixed with regression tests;
both Minor reporting/doc findings addressed. No second review was dispatched.
See privacy-review.md and final acceptance evidence in the verification report.

Acceptance: final macOS build, 110-patch/243-target pristine replay, Node 220 and
Python 19 passed (16 opt-in skipped), eight privacy and six network runtime
probes, eleven mounted-DMG probes. Packaged native UUID/stage hash and six
modified privileged resources match. Test mount detached; plan scratch removed.
No deferred Minor findings. Durable evidence: privacy-followup-verification.md.
