# Applicable Camoufox follow-up fixes for Firefox 157

User request: add the other Camoufox patches on the existing Firefox 157 branch. Preserve the completed generation checkbox and all existing container/site policies.

Upstream baseline: daijro/camoufox d01b8b907af0372b5c5a0f338cb94d2b2276db8c (patch contents unchanged from the prior audited f008b768 revision).

## Task 1: Native privacy and correctness
- Write regressions for live WebGL state/context attributes, version/extension gates, null capture fallback, analyser reads, owner principals, and configured-voice errors. Run against current source/binary; expect demonstrated failures.
- Port fixed-limit-only WebGL table reads, native mutable state and actual context attributes, owner-principal container resolution including detached documents and offscreen globals. Preserve renderer/vendor and site readback policy.
- Noise an analyser output copy while retaining current site/container seed selection. Allocation failure and disabled/no-seed remain native.
- Suppress backend voice-list errors only when a configured voice list is active; native mode still forwards errors.
- Append ordered native patches; prove the same behavior after incremental native build. Expected: all new regressions pass.

## Task 2: Resources and build platforms
- Restore stock crash-page resources even when crash reporting is disabled; remove development helper registration, packaging and startup call together.
- Add cloakfox.exe.manifest from the current stock Firefox manifest, preserving execution privileges/OS compatibility.
- Exercise the actual Rust target selector; add unique unknown-vendor fallback only where current selection is ambiguous, preserving exact matches and ambiguity errors.
- Expected: real selector tests, manifest XML checks and package/resource checks pass. Windows/Linux runtime builds are not available on this macOS host.

## Task 3: Verification and delivery
- Replay the full ordered patch stack into a separate selective pristine-source fixture, checking no offset/fuzz/drift.
- Run focused source tests, Node suite, native runtime regressions, and the preserved clear-overrides UI regression.
- Fresh final reviewer checks scope, native/patch consistency, OOM, invalid WebGL enum paths, offscreen ownership and platform fallback selection.
- Package macOS DMG, rerun local native regressions on the mounted package, and refresh hashes, patch count and TODO evidence.
- Commit the scoped changes and retain the branch for review. Expected: verified development DMG; no user profile, installation, merge or push.

## Review Focus
WebGL lost contexts and extension/version validation must precede captured data; mutable values must reflect calls. Analyser smoothing state must remain unchanged even when allocation fails. Detached/worker owners must keep their own identities. Native speech errors must survive with privacy disabled or no configured voices. Build selection must not pick incompatible ABI. All native changes must be reproducible by the patch stack.

Excluded: automation/Juggler, challenge or proctoring bypasses, fabricated capture/codec support, and removal of daily-use browser features.
