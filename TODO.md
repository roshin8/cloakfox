# Cloakfox — todo

Audited 2026-10-10 against source and recorded verification. Each item’s status
distinguishes unfinished implementation, missing verification and work awaiting
integration. [Per-item evidence](docs/todo-status-audit-2026-10-10.md); detailed
history remains in [PENDING.md](PENDING.md). Checked reconciliation tasks are
completed audits, not claims that every related feature is implemented.

## Current work

- [x] **Implemented on Firefox 157:** Native window/worker Performance Timeline presentation, real-backed media caps and generic labels, HDR masking and Settings controls. Timing mode changes apply on page reload/worker restart.
- [x] **Measured on Firefox 157:** Local TLS/H2/QUIC/H3 structural parity against stock Firefox; automatic network profiles follow the actual engine. WebSocket proxy/refusal/reconnect routes tested. [Evidence](docs/firefox-157-port/privacy-followup-verification.md).

- [ ] **In progress:** Finish TestDome owner-based screen geometry and Settings controls (in progress).
- [ ] **Not implemented:** Implement the native screen-details API and configurable screen count.
- [ ] **Not implemented:** Complete screen-management permission and Permissions Policy handling.
- [ ] **Partial:** Verify recording, package/sign the compatibility build, and check TestDome
  onboarding. These four tasks follow the [approved plan](docs/superpowers/plans/2026-10-10-testdome-native-screen-management.md).
- [ ] **Partial:** Verify actual screen, camera and microphone capture plus remote viewer
  delivery. Synthetic recording and local sharing indicators do not establish
  full TestDome or HackerRank media compatibility.
- [ ] **Partial:** Complete the Cloudflare Chrome-identity diagnosis: check relevant API
  availability/values. Matching appVersion still loops; the access trace does
  not establish the rejection cause. Firefox identity has passed.
- [ ] **Not verified:** Confirm the Settings startup/scrolling fix in the user's existing profile;
  fresh-profile and packaged probes passed, but that confirmation is outstanding.

## Firefox 155 worktree — separate privacy backlog

Source: [pending privacy plan](.worktrees/firefox-155-compat/docs/superpowers/plans/2026-09-09-pending-privacy-signals.md)
and [completion report](.worktrees/firefox-155-compat/docs/privacy-completion/README.md).
Historical work belongs to `codex/firefox-155-compat`. The active development
branch is `codex/firefox-157-port`; completed 157 follow-ups are labeled below. Its unchecked plan boxes do not by themselves establish status; the labels below
reflect current source and recorded acceptance evidence.

- [ ] **Partial:** Finish persisted generated-persona schema/provenance migration and standardized OS font inventories. Heuristic migration exists; versioning and removal of seed-random optional font membership remain.
- [ ] **Partial:** Verify bounded, deterministic font metrics across reloads, sites and frames.
- [ ] **Not implemented:** Gate IP-conflict-sensitive navigation before the first destination request;
  cover proxy changes, cache expiry, lookup errors and a scoped continue-once action.
- [ ] **Not implemented:** Compare and normalize WebRTC SDP/capabilities against stock Firefox;
  address-leak controls alone do not verify SDP coherence.
- [x] **Verified on 157:** Repeatable local TLS ClientHello baseline against stock Firefox, including certificate rejection controls.
- [x] **Verified on 157:** QUIC handshake/transport parameters and H3 SETTINGS captured locally; native randomized extension order retained.
- [x] **Verified on 157:** Local ws/wss handshakes, proxy routing, blocked/dead-proxy refusal and reconnect. Existing DNS route controls retained.
- [ ] **Partial:** Make persona application atomic across tabs, frames, workers and caches;
  prove no mixed configuration revisions survive.
- [ ] **Not implemented:** Decide and implement the Firefox 155 plan’s removal of optional Math-constant noise. Default constants are already exact; the optional path remains.
- [ ] **Partial:** Build the GPU/audio/media-device differential matrix and document residual
  platform differences; repair only demonstrated contradictions.
- [ ] **Pending integration:** Review and integrate the worktree's verified privacy changes with a clear
  commit/build baseline, preserving its uncommitted work and separate results.

## Release and platform work

Source: [release activation requirements](.worktrees/firefox-155-compat/docs/release/authenticated-updates.md).
Development signing and local fixture tests do not complete these tasks.

- [ ] **Blocked:** Configure owner MAR trust/signing keys and HTTPS update hosting.
- [ ] **Blocked:** Verify real signed-update installation, wrong-key/tamper/downgrade rejection,
  rollback and interrupted-update recovery.
- [ ] **Blocked:** Activate Safe Browsing with a working provider key and verify actual list
  downloads, freshness and failure reporting.
- [ ] **Blocked:** Complete macOS Developer ID signing and notarization for distribution.
- [ ] **Not implemented:** Integrate and verify Windows Authenticode signing.
- [ ] **Not verified:** Produce and runtime-test Windows builds, including install/update behavior.
- [ ] **Not verified:** Produce and runtime-test Linux builds and distribution packaging.
- [ ] **Partial:** Run the full privacy, network and release suite on each supported platform;
  compare foreign-OS personas and document rasterizer/graphics limitations.
- [ ] **Pending integration:** Integrate Firefox 155’s implemented engine-freshness CI gate into the chosen release baseline and verify each engine rebase; gate implementation itself is done there.

## Future / deferred

- [ ] **Deferred:** Evaluate native Chromium engine support: switch to Chromium or support
  both Gecko and Chromium, using the matching engine for each browser identity.
  Assess porting privacy protections and container/domain isolation, engine
  selection, packaging, and ongoing security updates; build a compatibility
  prototype before choosing the architecture.
- [ ] **Deferred:** Revisit SharedArrayBuffer timing privacy after reliable distinct-persona,
  cross-session/device linkability and performance measurements. Keep mitigation
  off as previously requested.
- [x] **Done:** Keyboard-event own `timeStamp` leak fixed by `ce347d05d3`; inherited getter and live nudge/ownership regression are recorded.
- [ ] **Partial:** Verify comprehensive bundled-font packaging/runtime on Windows and Linux. macOS pack/rendering is done; separate OS directories are optional if one pack passes parity checks.
- [ ] **Optional:** Extend Noto coverage for additional scripts / Japanese, Korean and
  Traditional Chinese if those languages become supported targets.
- [x] **Integrated on 157:** Native Performance Timeline coverage with exact owner/site keys; all three worker kinds covered. SAB mitigation remains separately deferred.
- [x] **Verified on 157:** HTTP/3 SETTINGS measured on local wire fixtures and compared with stock Firefox.
- [ ] **Deferred:** Keep TLS fingerprint modification as a separate deferred NSS project;
  baseline measurement is tracked above and does not authorize implementation.

## Older items — status needs rechecking

- [ ] **Not verified:** Recheck anti-bot battery reliability, especially `areyouheadless` timeouts,
  against the current build and site behavior.
- [ ] **Not verified:** Recheck headless inner/outer/screen geometry coherence and distinguish
  harness artifacts from behavior in a normal browser window.
- [x] **Audit complete:** Audited/retired obsolete MAIN-world migration, double-spoofer, container-isolation, branding-asset and CreepJS-selector backlog claims. Current WebGL/coherence runtime coverage still needs verification.
- [ ] **Pending documentation:** Refresh `docs/fingerprint-coverage.md`, the actor README and historical
  architecture inventory: they still describe removed injection/header-spoofer
  paths and make coverage claims that need current runtime evidence.
- [x] **Audit complete:** Audited original roadmap status: proxy controls/site exceptions are verified in Firefox 155; other roadmap candidates require decisions and acceptance evidence. See the audit’s roadmap reconciliation.
- [x] **Audit complete:** Audited `font:seed`: emitted but no native consumer found. Dormant metadata; optional cleanup, not an active font-spacing defect.

## Upstream review — 2026-10-10

- [x] **Development port verified:** Firefox 157.0.1 on `codex/firefox-157-port`; native macOS build, patch replay and local acceptance pass. Distribution and other-platform gates remain above.
- [x] **Source/package verified:** Added the Windows manifest and stock crash resources; removed paired development-helper startup/registration/resources. Rust Linux vendor fix already present and behavior-tested. Windows/Linux native runtime builds remain unverified. [Source findings](docs/upstream-patch-audit-2026-10-10.md).

## Additional upstream privacy fixes — source audit

- [x] **Implemented and runtime verified:** WebGL mutable state/actual attributes, fixed limits, null fallback, renderer coherence and version/extension errors. See [follow-up verification](docs/firefox-157-port/upstream-followup-verification.md).
- [x] **Implemented and runtime verified:** Analyser noise applies to output copies with existing site seeds; float/byte repeated reads, master-off and allocation-failure controls pass.
- [x] **Implemented and runtime verified:** WebGL owner principals preserve identities for attached/detached documents, DOMParser, createHTMLDocument, OffscreenCanvas and workers in two containers.
- [x] **Implemented and runtime verified:** Speech backend errors are suppressed for active environment-configured voice lists; no-list and master-off controls still forward errors. [Evidence and further conditional differences](docs/upstream-patch-audit-2026-10-10.md#follow-up-fingerprintingprivacy-behavior-comparison).
