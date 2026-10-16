# Chromium hosted checkpoint build implementation plan

> For agentic workers: execute inline using superpowers:executing-plans; user already requested implementation without plan approval.

**Goal:** Finish the pinned Chromium/CEF source build across standard hosted Mac jobs without exceeding their six-hour limit.

**Architecture:** Four sequential source jobs share a compressed, same-run workspace checkpoint, preserving source, generated files, Ninja state, objects and timestamps. Each compilation segment runs at most 180 minutes, leaving room for checkout/bootstrap and checkpoint compression/upload. Later jobs restore only matching commit, source/patch locks, root path, Xcode/SDK and runner image; they do not rebuild a fresh source tree. Completed compilation proceeds through SDK/client packaging, hash checks and existing mandatory runtime gates. Exhausting all segments fails the build gate.

**Tech stack:** Python stdlib tar/gzip, existing Ninja pipeline, GitHub reusable workflows/artifacts. No paid runners, source-mask changes, weakened tests or local build work.

## Constraints / review focus

- Current running jobs must not be cancelled. Keep pending successor concurrency.
- Preserve the complete workspace instead of forcing timestamps or assuming compiler caches fit.
- Reject changed archive bytes, wrong commit/toolchain/root and traversal or external links before resuming.
- Maintain 10GiB reserve during checkpoint creation/extraction; log checkpoint bytes and timings. Hosted storage/upload duration remain measured verification, not assumptions.
- SIGINT only the owned Ninja process group at the segment deadline; distinguish intentional checkpoint from genuine compiler failure.
- Runtime/coexistence artifacts must come from the same run/commit and actual source/SDK/embedded SHA checks.

## Tasks

- [x] Checkpoint helper and real-file tests: exact content/mtime/internal-link restoration; reject checksum/identity/path escape and insufficient space.
- [x] Timed compiler stage integration and real-child tests: intentional deadline yields checkpoint result, nonzero before deadline remains failure, resuming uses verified workspace with inherited locks.
- [x] Reusable source-segment job and four-step orchestration; hard final gate and conditional completed artifacts, preserve raw evidence at every segment.
- [ ] Full CI helper suite, actionlint, independent review, explicit-file commit/push. Verify active job remains intact and successor queues. Hosted large-checkpoint/source/runtime success remains pending until observed.
