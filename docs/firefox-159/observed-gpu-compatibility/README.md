# Firefox 159 observed GPU compatibility

This optional mode adds complete, recognized Windows Intel, AMD and NVIDIA
reference records while retaining the canonical software renderer and existing
readback, container-owner and site-secret protections. It is not physical-driver
emulation or a claim that the browser is indistinguishable from stock hardware.

## Scope and controls

In the selected container's Graphics section, enable **Use observed GPU
compatibility** after enabling the existing reference-profile option. Canonical
software rendering and container-specific GPU persona profiles are prerequisites.
The mode defaults off. Its saved request is `rendering:gpu_observed`; descriptors
use version 4, `observed-reference`, exact owner and a complete immutable catalog.
Reload pages and restart workers after changing it.

Disabling this option returns to the existing reference mode. Disabling reference
profiles also clears the observed request atomically. Unsupported identities are
rejected before persistence; the browser does not silently rename a GPU or fall
back to the physical host. Other containers' preferences and secrets are retained.
Public capability values can coincide between containers; their records and
identity secrets remain separately owned.

| Code | Compatible recorded Windows persona |
| --- | --- |
| 36866 | Intel HD Graphics 400 |
| 36867 | AMD Radeon R9 200 Series |
| 36868 | NVIDIA GeForce GTX 980 |

Apple remains supported by the previous protected reference mode. The pinned
Apple observations contain precision/varying/timeout behavior the canonical
backend cannot truthfully reproduce, so Apple is not admitted to observed mode.

## Native behavior

The selected contexts initialize real front/back stencil masks to 0x7fffffff.
Author changes remain mutable and affect drawing. Typed shader translation clamps
implicit texture bias to [-2, 2], evaluates expressions once, and leaves explicit
LOD, gradient, fetch and author-defined calls alone. The compiler resource key
includes this policy. WebGL2's 0xfffffffe maximum agrees with its existing legal
0xffffffff fixed-restart marker. No source-text substitutions or detector-specific
runtime branches are used.

The three complete numeric parameter/precision vectors come from the immutable
source archive. Existing four reference records are unchanged. Debug shader/timer
extensions remain excluded, precise readback guards remain enabled, and the
signed canonical CPU backend is unchanged.

## Validation and provenance

Acceptance passed on the separate headless Firefox 159.0-beta.1 app recorded in
`acceptance-app.json`. See `acceptance-summary.json` and the raw phase receipts.
No installed application or personal profile was changed.

- Six native probes passed, including 1,431 observed-mode checks across six owners,
  WebGL1/WebGL2, pages and workers; 82 actual settings checks passed.
- All 22 broader graphics/font/geometry probes passed after the targeted font
  fixture correction described below. The initial failed receipt is retained;
  `font-runtime.json` records its passing rerun.
- JavaScript: 392 passed; Python: 196 passed; CI helpers: 16 passed, no skips.
- Unmodified CreepJS and FingerprintJS: 144 executions across three modes, eight
  cases per mode and three repeats, with WebGPU enabled. All assertions passed.
- Observed Intel, AMD and NVIDIA profiles have no CreepJS “suspicious gpu” or
  “suspicious capabilities” warnings. Firefox-identity samples also have no
  reported CreepJS lies in this fixture. Chrome-identity samples retain the
  known SpiderMonkey/V8 user-agent mismatch; recognition is not invisibility.
- The incremental native build passed with 28 suppressed third-party warnings.
  The reviewed native/source/resource hashes still match the tested app.

- Native patch source hashes: `native-source-freeze.json`.
- All 168 maintained patches replay without fuzz/source differences: `patch-replay.json`.
- Full unit suites and CI helpers: `unit-tests.json`.
- Offline full-source projection: `observed-record-audit.json` and
  `scripts/audit-observed-gpu-profiles.cjs`.
- Independent review: `code-review.md`.

Pinned CreepJS commit: `10aa6724cd33a1015db1574211890518cd04f0cc`.
Bundle SHA256: `80f43f364bd973bc03cb5b82de033ce28b2bbb145cb04237632a46ef040a92be`.
The library fixture is unmodified. Production admission uses complete reference
records, never CreepJS allowlist hashes. Recognition assertions require an actual
collected WebGL result with parameters and a warning list, not merely absent
warnings after failed collection.

## Test fixture repairs

Review found a vacuous absent-warning assertion; it now requires collected WebGL
and has negative tests. The back-facing stencil fixture initially used unequal
effective front/back state, which WebGL correctly rejected; it now uses legal
matching references/masks with different comparison functions and checks real
pixels plus GL_NO_ERROR. The settings probe centers real controls before native
clicks to avoid the fixed header. The geometry probe waits for asynchronous window
resize to reach content before comparing measurements and screenshots. A follow-up corrected the test helper’s chrome-to-content context switch before reading the viewport. None of
these repairs weakened production validation or removed rendering assertions.

The font-spacing regression fixture previously omitted its internal HMAC secret,
allowing startup to generate random inputs; two noisy widths happened to collide.
It now pins a public disposable secret and verifies actual fonts/seed/secret before
measurement. The same assertions pass: baseline1096.05005px, A1102.05005px, B1104.05005px,
with A unchanged after restart. No production font policy changed.

Chromium committed build-input key is unchanged:
`bbc651dcf5cbe4321f5fd1728eb40f2a20f7547053009258d96764370804dfcf`.
All earlier checkpoint ancestors are retained. Only generated Gecko inventory
metadata changed under `engines/chromium`; no Chromium build input or process was
modified. Validation is on this Mac and does not establish other-OS rendering.
