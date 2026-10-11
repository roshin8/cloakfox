# Daily-driver privacy implementation plan

> Use superpowers:subagent-driven-development for independent bounded tasks, with controller integration and review. Preserve all existing uncommitted port work; do not commit, merge, publish, or alter the original checkout.

**Goal:** Implement the accepted privacy audit recommendations as independently tested changes in the Firefox155 worktree.
**Spec:** docs/privacy-feature-gap-audit-2026-09-07.md, approved by the user's “work on these”.
**Architecture:** Preserve native C++ plus privileged actors. Reuse Firefox services for preferences, data clearing, isolation and networking. Defaults remain usable for ordinary browsing; stronger network policies must be explicit and fail closed when selected. No remote debugging or mandatory cloud account.

## Tasks

- [x] 1. Derive persona UA version from build metadata and migrate stale generated identity fields while preserving seeds and explicit overrides; regression tests.
- [x] 2. Restore protective daily defaults (Safe Browsing, HTTPS-Only), make ordinary choices persistent, expose necessary native browser UI; startup/restart verification.
- [x] 3. Implement an explicit container-data forgetting workflow distinct from appearance changes, with scope/confirmation and failure handling; isolated browser tests.
- [x] 4. Remove automatic third-party IP-echo contact from default browsing; implement explicit WebRTC/network controls and accurate status. Establish per-container proxy/no-fallback enforcement and test failure behavior.
- [x] 5. Implement site-keyed protected fingerprint outputs with context propagation across C++/actors/workers and stable reload behavior; verify cross-site separation and compatibility.
- [x] 6. Integrate maintained blocking and per-site recovery, retaining user control and list updates.
- [x] 7. Implement site-container rules, temporary containers, and safe profile backup workflow.
- [x] 8. Implement authenticated update/release support and status. Production publishing/signing is gated on actual owner-controlled keys/hosting; never ship an invented trust root or downgrade protection to make a demo pass.
- [x] 9. Expand daily-driver regression coverage, reconcile source patches/additions, build, review and document remaining platform/deployment limits.

## Verification and coordination

Use failing behavioral regressions before feature changes. Pure tests run in Node; live tests use disposable Selenium profiles with system access. Workers own disjoint files; controller integrates shared UI/build files sequentially. Existing _READY source must not be patched twice. Additions and owning patches are the source of truth. Tests must not erase real profiles or modify original checkout.

Track concrete results and unresolved work in docs/daily-driver-privacy/progress.md. Independent source review follows each implementation. Run live test suites sequentially to avoid build/profile interference.

Completion scope: task8 delivers authenticated release support and visible readiness; production update deployment and Safe Browsing provider activation remain owner-configuration requirements, as explicitly scoped above. Final evidence: docs/daily-driver-privacy/README.md.
