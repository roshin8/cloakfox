# Container rendering profiles: feasibility gate

Status: implementation started with plan Task 1; no product code, settings, persona records or installed app changed. The user requires physical Apple/Intel/AMD/NVIDIA support. SwiftShader-only support is not sufficient. This report does not claim that the proposed toggle or separate native GPU profiles have been implemented.

## Fresh installed baseline

Binary `/Applications/Cloakfox.app/Contents/MacOS/cloakfox`, BuildID `20261015160908`; full XUL checksum and raw measurements in [feasibility-final/result.json](feasibility-final/result.json). The new disposable-profile probe is `tests/fingerprint/probe_container_rendering_feasibility.py`.

25 baseline checks pass: real owner IDs, existing protected canonical modes, actual WebGL1/2 operation, enabled WebGPU operation and actual software-backend texture allocation bounds. This is a baseline, not acceptance of the new feature.

For each of Windows/NVIDIA, macOS/Apple and Linux/software, two real containers receive identical generated BrowserForge persona inputs while retaining independent original seeds. Every pair has different intrinsic text geometry and canvas output, but an identical reported GPU tuple (`Mozilla`/`WebGL`, 2048 texture ceiling, 32 combined texture units). This confirms why merely storing another per-container record cannot satisfy the proposed independently enforced GPU profiles.

The diagnostic raw software-backend control removes the reporting/profile masks in a disposable container while retaining canonical CPU backend routing. Its actual texture maximum is 8192; width 8192 succeeds and width 8193 is rejected with INVALID_VALUE in both WebGL versions. Current `CloakfoxPersonas.GL_BASE` emits 16384 for texture size. This is Cloakfox's derived generic table, not a capability guarantee supplied by BrowserForge. Copying it cannot produce an enforceable backend profile. The diagnostic bypass must not become a product mode.

## BrowserForge catalog gap

Exhaustive positive-probability traversal of the shipped network finds 10 root UAs and 21 reachable GPU choices. No positive-probability SwiftShader combination exists. The reachable software renderer is `llvmpipe, or similar`, vendor Mesa. SwiftShader appears in the broad possible-value vocabulary, which is not equivalent to a reachable coherent sample. See [browserforge-support.json](browserforge-support.json).

Therefore a SwiftShader-only first implementation needs compatible BrowserForge data/filtering and validation too; it must not relabel the saved llvmpipe or physical-GPU persona. Supporting physical Apple/Intel/AMD/NVIDIA identities also needs a reference profile and verified execution/emulation coverage, beyond the current common bounded profile.

## Current execution boundary

The user answered: physical Apple/Intel/AMD/NVIDIA personas are required. That decision is settled. Existing personas remain preserved. The current backend has no validated complete hardware-emulation catalog for these families; see [required-hardware-coverage.json](required-hardware-coverage.json). A collected renderer label or static capability table does not supply that missing execution behavior. No production toggle should be added that silently substitutes a shared profile, fabricates a hardware label, or appears active while only the old common GPU profile runs.

Existing canonical font infrastructure already reaches `gfxFontGroup` and uses owner/site-specific scale. The remaining geometry work must evaluate non-font platform layout/control inputs before replacing return-value guards. This report does not prove complete protected layout coverage.

Next execution must resolve the supported catalog, complete Task 2's exact enforcement contracts and then implement/test the toggle and native paths. No new completion claim, build, installation or publication was made.
