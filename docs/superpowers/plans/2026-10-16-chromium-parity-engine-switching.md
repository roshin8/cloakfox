# Chromium parity and same-window engine switching implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete native privacy parity and select a real, protected Chromium page in the existing Cloakfox window when a Chrome identity is chosen.

**Architecture:** Gecko owns trusted UI and per-container engine intent; a packaged, isolated CEF helper owns Chromium pages and engine-specific stores. An authenticated native offscreen surface/input bridge presents Chromium in the existing viewport. A complete versioned privacy snapshot and verified native capabilities gate all navigation; current Gecko identities remain coherent until a real switch commits.

**Tech stack:** Maintained Gecko158, pinned Chromium154/CEF source, C++/Objective-C++, privileged Gecko modules, inherited pipes plus native Mach surface rights, macOS arm64 acceptance.

**Spec:** `docs/superpowers/specs/2026-10-16-chromium-parity-engine-switching-design.md`

## Global constraints

- The user selected same-window switching on 2026-10-16 and later requested a per-container same-window/separate-window setting. Same-window remains default; both modes share the complete release gate, with no automatic fallback. The external build drive is available. Proceed inline; no further design-question round is necessary.
- Preserve the protected Gecko installation, all saved profiles, and all pending prior source changes.
- No production CDP, page bindings, MAIN-world injections, unsandboxed rendering, test-Keychain mode or public controller endpoint.
- Apply immutable engine/container/site/private policy before page/worker/network startup. Unsupported protection fails before a request; it is not release completion.
- Persistent stores and private lifetimes remain engine/container-owned. Default container 0 maps explicitly and must not alias container 1.
- Do not mutate native source inputs during an active source build; preserve SDKs/artifacts and use reviewed input hashes.
- Full runtime/privacy acceptance plus independent whole-change review is required before replacing the installed release or reporting completion.

## Review focus

- Startup, workers and preconnects before config acknowledgement: no request or unmasked first script.
- Active edits/media and cancellation during switching: no data loss, silent capture stop or wrong-engine identity.
- Stale/private/deleted owners and helpers crashing: no reused context, resource or private seed.
- Surface/input messages with stale revisions or invalid dimensions: no wrong-tab pixels/keystrokes, out-of-bounds reads or exposed native handles.
- Normal restart/update with old startup caches and a mismatched helper: refuse incompatible routing and retain the protected engine.

## File and interface map

- Existing native identity increment: `engines/chromium/{apply_identity_patch.py,build_identity.py,identity-patch-lock.json,patches/native-identity-locale-privacy.patch}`, `src/{persona_config.*,browser_client.cc}`, `engines/shared/persona_config.py`.
- `engines/chromium/src/offscreen_client.*`: CEF windowless browser creation, owned-frame copies and native input delivery. Emits bounded native frame events; no pointer/handle JSON exports.
- `additions/cloakcfg/engine-host/surface_transport_mac.*`: inherited native endpoint bootstrap and per-tab Mach send-right transfer, owner/revision validation and shutdown.
- `additions/widget/cocoa/CloakfoxEngineHost.*` plus an ordered native patch: privileged viewport composition/input/accessibility, with a chrome-only XPCOM service interface. No page-callable method.
- `engines/shared/engine_policy.py`: engine intent resolution, external/internal container mapping, versioned group capabilities and complete policy validation.
- `additions/browser/components/cloakfox/CloakfoxEngineController.sys.mjs`: packaged helper launch, trusted snapshot generation, acknowledgements and atomic tab replacement. Shares typed contract with the native host, not Python at runtime.
- Existing settings/BrowserForge/override modules: display desired and actual engine, persist intent and validated shared policy, retain coherent backend-specific UA overlays.
- Native privacy groups: separate ordered `engines/chromium/patches/native-<group>-privacy.patch` and `*-patch-lock.json`; common immutable browser/renderer/worker policy plumbing must be shared rather than copied per vector.
- `tests/engines/`: local fixtures, unit/C++/native and cross-engine UI probes. Evidence under `docs/dual-engine/parity-20261016/`.

### Task 1: Verify and recover pending native identity build

Consumes existing pinned source/SDK/build pipeline. Produces a runtime-verified identity-capable companion; does not claim general parity.

- [x] Inspect pipeline/process/source locks; verify existing source hashes and embedded framework against its SDK provenance.
- [x] Run complete engine tests with the built identity app, including five identity runtime cases; diagnose every failure by its first failing assertion. Expected: all implemented-feature tests pass, no hidden skip or unsupported capability.
- [x] Run CTest, owned isolation/transport and versioned dual-engine coexistence. Expected: sandbox/certificate refusal and independent stores preserved.
- [x] Correct the stale Gecko source inventory for actual changed first-party files; preserve the meaning that inventory coverage is not privacy coverage.
- [ ] Update evidence and pending identity status only from fresh successful results. Commit only scoped completed files, preserving unrelated work.

### Task 2: Prove CEF windowless rendering without losing native policy

Consumes Task 1 SDK and existing versioned context acknowledgement. Produces optional development-only `--windowless` rendering with bounded frame metadata; default windowed behavior remains covered.

- [x] Write `tests/engines/test_offscreen_rendering.py`: unsupported baseline flag must fail the intended acceptance; candidate must render an owned fixture without a visible CEF top-level window, acknowledge the owning browser, preserve configured first-script identity and canvas protection, and reject unconfigured/stale ownership.
- [x] Implement `offscreen_client.*`, wire into existing `CreateBrowser`, and enable CEF windowless settings only for the explicit mode. Use Alloy style required by the pinned CEF API while retaining the same owned request context. No permission/security exception.
- [x] Test CPU and accelerated paint callback lifetimes locally, frame bounds, popups, resize, scroll and native input; copy each accelerated frame into owned storage before callback return. Expected: observable fixture pixels/input with correct owner/revision, no raw-pointer IPC.
- [ ] Run the complete engine suite, C++ tests and native policy tests in both presentation modes. Record feasibility limits honestly.

### Task 3: Present the Chromium surface in a Gecko native viewport

Consumes Task 2 owned surfaces and native context ownership. Produces the chrome-only host service and authenticated `attach/detach/resize/input/frame` contract keyed by tab token and config revision.

- [x] Write native transport tests for stale/replayed tokens, unknown senders, invalid dimensions/stride, oversized frames, helper death and cross-tab input; expected rejection before mapping/delivery.
- [x] Implement authenticated per-launch rendezvous, Mach-right ownership and bounded copies in `additions/cloakcfg/engine-host/surface_transport_mac.*`; never publish global surface IDs or page-visible native handles.
- [x] Implement `CloakfoxEngineHost.*` and its build/IDL patch. Local fixtures only until the release gate exists. Render the surface in the existing content viewport without starting a separate top-level CEF window.
- [ ] Add real Gecko/CEF fixture tests for resize/retina, scrolling, keyboard/IME/focus, popup painting, drag/drop, occlusion, accessibility, video and tab close/reopen; wrong tab must receive neither pixels nor input. Expected: native functionality and owner checks pass together.
- [ ] Whole-boundary source review before exposing any ordinary site through the host.

### Task 4: Complete policy schema, capability registry and engine selection contract

Produces `resolve_engine(ua, versions)`, `backend_container_id(external_id)`, `validate_policy(snapshot, capabilities)` and immutable schema2 snapshot/acknowledgement models consumed by all later groups and controller.

- [ ] Write table-driven tests: Firefox->Gecko, Chrome/Chromium->Chromium, unsupported Edge/custom versions rejected; external 0 and 1 map differently; strict booleans/integers/field sets, private ownership, every required capability and stale revision fail before `open`.
- [ ] Implement complete group registry and schema2 with per-group native versions, actual engine version, effective BrowserForge persona and active options. Keep legacy v1 development tests explicit; do not upgrade records silently or equate a feature list with verified code.
- [ ] Native and controller negative tests must prove no request occurs for missing/rejected policy and no sensitive data appears in acknowledgements. Preserve source-site/container key derivation.

### Task 5: Native full BrowserForge identity and regional parity

Consumes schema2 and pending native identity implementation. Produces native identity/region group capabilities with full supported overrides.

- [ ] Extend local fixtures for BrowserForge OS/hardware/locale presets, arbitrary supported canonical languages/timezones, request and JS hints, appVersion, platform, memory, touch and first-script/frame/all-worker ownership.
- [ ] Extend pinned native hooks in Blink Navigator/WorkerNavigator, browser request/client-hint services and ICU/V8 initialization; validate complete personas before context creation. Actual Chromium version/brands remain coherent.
- [ ] Test two containers/sites, persistent/private restart, regeneration/overrides and independent toggles without host fallback. Build/replay/source-hash/runtime acceptance before declaring the group supported.

### Task 6: Native display, geometry and bundled fonts

- [ ] Add independent expected-value fixtures for JavaScript/CSS/viewport/screen agreement, rectangle unions/carets/transforms and bundled font glyph/fallback/FontFace behavior in pages/frames/workers.
- [ ] Port at Blink screen/layout/font native paths; adapt bundled canonical font resources without reading host font lists for protected contexts.
- [ ] Verify layout/input/selection functionality, locale/script coverage and persona/site/container isolation; invalid/unsupported profiles refuse activation. Build/replay and full affected runtime suites.

### Task 7: Complete canonical canvas and GPU provenance/resource parity

- [ ] Port independent Gecko canvas/encoder/SVG/text/media/foreign-owner fixtures to Chromium, including HTML/OffscreenCanvas/all worker types/bitmaprenderer/async snapshots/WebGL PBO and WebGPU copy/map paths.
- [ ] Reuse reviewed portable renderer/resource components where compatible; implement native Blink/Skia/ANGLE/Dawn adapters and producer qualifications. No unqualified raw output on failure.
- [ ] Enforce actual bounded Apple/Intel/AMD/NVIDIA profile capacities and shader/resource limits, with the same existing optional toggle semantics. Test actual allocation/compute and all readback/export routes at reported bounds.
- [ ] Full native builds, local pixel goldens and adversarial owner/readback tests with toggles both ways; no physical-driver emulation or detector-score claim.

### Task 8: Native audio, codecs and media presentation

- [ ] Port independent page/worker/AudioWorklet/OfflineAudioContext fixtures for noise, sample/latency, copy/analyser paths, codec/capability/HDR coherence and private owner lifetimes.
- [ ] Implement native Blink audio/media/WebCodecs presentation, preserving normal playback/capture and exact numeric/data correctness.
- [ ] Test alternate paths cannot read host outputs; run native fixture suites and update group capability only after build/runtime acceptance.

### Task 9: Native clocks, scheduling and math

- [ ] Port clock/timeline/observer/worker/worklet tests and local scheduling/math data-correctness tests, including background/foreground and immutable mode across restart.
- [ ] Implement native Blink/V8/browser scheduler equivalents for active settings, preserving existing precision/data-noise choices and timing ownership.
- [ ] Verify no contradiction between clock surfaces and no broken arithmetic, event delivery or animation/input. Build/replay and full affected suites.

### Task 10: Native input, optional hardening and remaining devices

- [ ] Inventory and port each actual keyboard/clipboard/activity/fullscreen/name/EME/notification/persistence/device/feature option, with native input and accessibility controls.
- [ ] Implement browser/Blink native paths rather than exported MAIN-world wrappers. Retain field-to-field focus, trusted editor input and meaningful permission behavior.
- [ ] Local fixtures prove masking and functional editing/menus together; disabled controls are isolated to disposable native-control tests. All options retain their saved intent per owner.

### Task 11: Native permission, media, WebRTC and proxy privacy

- [ ] Add fake-device/local peer/TURN/proxy/DNS/HTTP/WebSocket fixtures proving native user consent, owned device IDs/counts/labels and positive transport alongside blocked raw-route/candidate leaks.
- [ ] Replace prototype deny-all callbacks with a trusted native permission broker. Port required proxy readiness/resolver/failover and independent opt-in IP lookup to actual Chromium network/WebRTC services.
- [ ] Cover startup workers, ICE restarts, required-proxy failure, proxy authentication and route changes; never direct-fallback. Physical Mac camera/mic/screen chooser tests require real user actions before final acceptance.

### Task 12: Storage, browser/network policies and production services

- [ ] Port fixtures for storage/worker/cache/connection/TLS-ticket isolation, exact-host routes, tracking/query/bounce controls, scoped deletion and routed opt-in dual-family IP warnings.
- [ ] Implement native ownership/policy plus production Keychain integration, preserving per-engine stores. Test restart/update rollback, private popup lifetime and container deletion/recreation.
- [ ] Authenticated H2/H3 and WebSocket route/certificate tests must pass; pre-certificate observations alone do not complete this task.

### Task 13: Trusted production helper controller and settings projection

Consumes fully passing Tasks 4–12 group capabilities and Task 3 host. Produces `CloakfoxEngineController` with `prepareSwitch/commitSwitch/cancelSwitch` and revision-bound tab/context state.

- [ ] Write privileged module tests proving a Chrome-family selection requests Chromium, keeps a live Gecko identity coherent until commit, preserves cancelled edits/media, and refuses missing helper/policy with zero site requests.
- [ ] Implement production inherited-pipe launch and native host integration; no Python/CDP dependency or test-Keychain flag. Apply all settings/BrowserForge overrides atomically through the shared schema.
- [ ] Wire actual/desired engine indicators, per-container same-window/separate-window presentation, and explicit apply/reload behavior into existing settings; aliases/branding do not decide engines. Changing presentation preserves saved identity/protection policy and uses the same commit/cancel transaction. Check Default/private containers and active opener groups.

### Task 14: Full same-window real-engine switching acceptance

- [ ] Owned fixture observes Blink/Chromium APIs and actual native Chromium wire behavior after selecting Chrome; Firefox selection returns real Gecko. Neither merely changing UA nor opening a companion window passes.
- [ ] Cover Back/Forward/Reload, session restore, edits/media cancellation, redirects, popups, helper death, tab/container deletion and two sites/containers across both engines. Stores/seeds never cross owners.
- [ ] Run the full two-engine UI/native/security suites and local pinned fingerprint libraries. Keep residual warnings visible and diagnose concrete privacy inconsistencies.

### Task 15: Reviewed installed release and final verification

- [ ] Package both engines/resources/helpers with versioned capability manifests and strict sandbox/signature/integrity checks; native application identity and update/rollback cannot silently re-enable old hooks.
- [ ] Dispatch independent whole-change privacy/security/native-host/IPC review; reproduce/fix findings with RED/GREEN plus relevant full-suite runs.
- [ ] Install only the verified release with recoverable old app. Test normal cached-profile startup, both real engines in one window and physical consent/capture locally. Generate matching verified DMG.
- [ ] Record exact versions/hashes, all test results, skips/blockers and remaining limitations. No completion claim while a required task is pending.
