# Chromium privacy parity and identity-driven engine selection

Status: user selected same-window switching and reattached the build drive on 2026-10-16; proceeding inline. Implementation and release acceptance are not complete.

## User requirements

Finish porting Cloakfox privacy protections to Chromium, make selection of a Chrome UA actually use Chromium, preserve privacy, test both engines, and run independent code review. The existing protected Gecko installation and saved profiles must remain usable. Initial physical-device acceptance is macOS arm64, consistent with the user's earlier testing scope; Windows/Linux results must not be claimed from Mac tests.

## Current evidence and dependencies

The maintained checkout is `/Users/zeus/.codex/worktrees/firefox-158-port/cloakfox`. Existing Gecko158 patches and `additions/` are the behavioral reference, including the keyboard lifecycle repair. The Chromium port is the CEF154 development companion under `engines/chromium/`. Native same-window fixture hosting now works; production tab routing and general privacy parity are not implemented. `feature-inventory.md` and `gecko158-inventory.json` are discovery inputs, not passing privacy evidence.

At the initial 2026-10-16 audit, the existing installed Gecko and local companion passed the concurrent owned-origin storage/lifecycle probe. All five `test_identity_privacy.py` runtime cases failed at missing `identityPrivacyVersion`. Uncommitted identity/config/source patches already exist; preserve and complete them rather than overwrite them. That initial SDK/app did not include the native increment; recovery has since built and runtime-verified it, as recorded in `docs/dual-engine/parity-20261016/native-host-status.json`. Chromium source is present at `/Users/zeus/cloakfox-builds/chromium/full-source/chromium/src`. Native outputs and SDKs require `/Volumes/CloakfoxChromiumBuild/source-build`; that volume was absent during the initial audit and has since been reattached. The internal filesystem had about 9 GiB free and is not an alternative native build location.

## Product behavior

A browser-family choice is engine intent, not an arbitrary UA-string substitution. Desktop Chrome/Chromium and Edge identity selections require the real Chromium backend; Firefox identity selects Gecko. An Edge brand must not be claimed merely because the CEF runtime is Chromium: unsupported branded configurations are rejected until their native identity semantics are implemented and tested. Custom version strings must not imply a different engine version; use the actual installed backend version, display the effective identity before applying, and reject incompatible custom strings rather than silently impersonate an unsupported version.

Only trusted settings actions change engine intent. A website changing a JavaScript property, sending a message, redirecting, or opening a popup cannot choose a backend or obtain controller access. Existing cross-engine spoofing modes must not silently remain active as the new routing behavior: current Gecko tabs keep a coherent Gecko identity until their replacement backend is ready.

The earlier roadmap constraint that UA edits never select engines is superseded by the user's explicit 2026-10-16 request.

The user selected same-window replacement and subsequently requested a configurable same-window/separate-window choice on 2026-10-16. Same-window remains the default. Persist the presentation preference per container; apply it through the same atomic switch transaction on explicit reload, without moving a live page or losing edits/capture. Separate-window uses its own engine-owned UI and stores and is never an automatic fallback for a failed same-window switch. Both modes require identical verified policy, permission, lifecycle, network and isolation guarantees. Same-window native surface/input/accessibility feasibility remains required; separate-window success does not complete same-window acceptance.

Engine selection is per container, including Default (external ID 0) and private-container ownership. The portable schema currently excludes 0 and needs an explicit Default mapping without colliding with real container 1. User-selected BrowserForge OS/hardware/locale and overrides remain container-owned. Derive engine/site keys with separate domains; do not reuse another container's record or publish a master seed to page code. Equivalent privacy policy does not require exposing identical cross-engine fingerprints.

Cookies, localStorage, IndexedDB, caches, service workers, authentication databases, TLS tickets and connections remain engine/container-owned. No cookie or password-database copying is part of switching. Returning to an engine restores its own existing session; private sessions are memory-only and destroyed after all owning windows/workers close. A site may require another sign-in when first used in the other engine.

## Atomic engine-switch transaction

1. Resolve requested family and canonical persona policy in the trusted settings controller. Validate the complete snapshot and all active required protections.
2. Verify packaged helper provenance, actual engine version, schema, native capability versions and resource manifests. A capability claim alone is not proof: the packaged revision must have corresponding passing native/runtime acceptance records.
3. Reserve the correct engine/container/private context. Apply immutable configuration and acknowledge its revision before any page, worker, preconnect, service-worker startup or site request.
4. Existing pages retain their actual engine and compatible identity while a switch is pending. Show desired and actual engine separately. On the user's reload/switch action, honor beforeunload and native active-media/loss prompts. Do not copy DOM/form state, submit forms, or silently stop an active capture. Cancelled switching leaves the old page intact.
5. Navigate only after the target context and presentation are ready. Commit the tab's engine/context ownership and update chrome UI atomically. Duplicate acknowledgements, helper death, outdated revisions, permission denial and renderer failure must not show a wrong-engine page or open an unprotected fallback.
6. Releasing the old tab stops its engine-owned activity when native page/lifecycle rules allow; no hidden old tab continues network/media activity under the new visible identity. Popups and named targets inherit the owning context and cannot migrate another opener group.

Unsupported policy or missing helper fails before a site request, retaining the existing protected page and reporting the missing capability. This is an intermediate guard, not a substitute for completing privacy parity. General engine switching is not release-ready while any required group remains unimplemented.

## Host and presentation boundary

Reuse the native CEF source build and inherited-pipe controller; production must not expose CDP, HTTP control ports, page bindings or MAIN-world inject scripts. The trusted Gecko parent owns UI, container intent and launch authority. A packaged native host owns CEF subprocesses, lifecycle and the versioned control transport. Production must not depend on Python being installed or enable the prototype test-Keychain mode.

If same-window is chosen, first prove CEF offscreen rendering can integrate with a Gecko native viewport without joining the engine runtimes in one process. The pinned CEF `OnAcceleratedPaint` API supports macOS IOSurface output, but the callback's surface may not be retained after return: copy into client-owned storage before an authenticated surface handoff. Native bounded surface/input/focus routing, popup composition, IME, drag/drop, accessibility, scrolling, video, occlusion, screenshots and display changes are required. No global IOSurface-ID lookup or public socket is acceptable. A rendering feasibility failure is reported, not disguised as successful shared tabs or replaced with a separate window without the user's choice.

If separate-window is chosen, retain existing CEF Views with a production controller and unambiguous actual-engine indicator. The same policy, lifecycle, permission and isolation requirements still apply. Shared bookmarks/UI preferences can be synchronized through typed trusted messages; sensitive engine stores remain separate.

## Required native parity groups

For each group, inventory every active Gecko setting and supported override, its Chromium hook, immutable owner data, all execution contexts, positive functionality and negative/privacy tests. Refresh the inventory against current first-party source. Do not equate matching option names, unit mocks, deny-all permissions or a `privacyPatched` flag with parity.

| Group | Required observable behavior and native integration |
| --- | --- |
| Identity and BrowserForge | Complete validated persona/override projection; coherent real engine UA, request headers, client hints, platform/oscpu where applicable, hardware, touch and memory. Native descriptor/brand behavior; before-first-script pages, frames and workers. Complete and build the pending identity patch before further native groups rely on it. |
| Display, DOM and fonts | Protected screen/window/viewport/CSS media and geometry agree with layout and letterboxing. Preserve rectangle unions, empty nodes, caret and transforms. Native bundled font selection, FontFace local-vs-URL rules, glyph metrics and fallback. No physical screen/font fallback for masked or unsupported personas. |
| Canvas and graphics | Preserve optional canonical rendering and strict producer/owner provenance through Canvas2D, HTML/OffscreenCanvas, bitmaprenderer, crop, exports/encoders, SVG, text/fonts, image/video/WebCodecs sources, WebGL direct/PBO/typed reads and WebGPU copies/maps. Native limits and actual allocation/shader/resource enforcement agree with configured Apple/Intel/AMD/NVIDIA bounded profiles. Cover stale/foreign owners and async completion; failed protection must not return raw pixels or host identifiers. Current opaque-RGBA transforms alone are insufficient. |
| Audio and codecs | Native AudioContext/OfflineAudioContext/AudioWorklet outputs, analyser/copy paths, sample/latency presentation, media capability/codecs/HDR and worker consistency. Preserve useful playback/capture and numeric correctness; no unmasked alternate readback. |
| Region and permissions | Native Date/Intl/language/header/timezone coherence and host-change suppression, valid explicit Intl arguments, consent-gated location presentation, native permission state and persistent/one-visit grants. Full supported BrowserForge regional range, not only the prototype's bounded presets. |
| Timing and arithmetic | Page/performance timelines, worker/worklet clocks, observer entries, scheduler/timer/animation options and immutable timing mode. Preserve arithmetic/data correctness and existing optional math semantics. No conflicting clocks or uncaught exported-wrapper errors. |
| Input and optional hardening | Native keyboard cadence, clipboard event/API options, focus/visibility/fullscreen/pointer/hover options, window.name, EME, notification/storage permissions and remaining feature/device controls. Preserve real input, intra-page focus, accessibility and ordinary editor behavior; distinguish synthetic from trusted-event test coverage. |
| Media, WebRTC and network | Functional camera/audio/screen selection with genuine user consent and OS permissions; masked device counts/labels and owned IDs; relay/proxy readiness before candidate gathering. Preserve required proxy routes, resolver/failover checks, DNS, HTTP(S), WebSocket Origin/cookies/headers and independent opt-in IP discovery. Never retry a required failed route directly. Owned fixtures prove positive media transport and negative leak prevention. |
| Storage and browser policies | Engine/container/private storage and worker isolation, connection/cache/TLS-ticket isolation, query stripping/tracking/bounce/site policies, exact-host routing and dual-family IP conflict records. Anonymous routed lookups stay opt-in; no claim that a lookup proves arbitrary destination egress. Deletion/recreation cannot revive old ownership. |
| Packaging and sensitive services | Both signed engines/helpers/resources in one validated release; stable application identity, native OS capture prompts, sandbox/entitlements, certificate validation, security updates and engine capability manifests. Production password storage must not use prototype mock/test Keychain. Update/rollback must never pair a newer UI with older privacy hooks silently. |

Absent engine-native APIs need an explicit applicability rationale and tests; do not add Firefox-only APIs to Chromium merely to make a table identical. Broader engine differences and static fingerprint-library warnings can remain while the stated privacy guarantees hold. Do not promise unidentifiability or physical-GPU driver emulation.

## Verification and release acceptance

- Use owned HTTP/TLS/H2/H3/QUIC/WebSocket/TURN fixtures and local privacy probes. Website bot-challenge acceptance is not a privacy-parity criterion.
- Both engines: Default plus at least two persistent containers, two sites, private sessions, reload/restart, navigation and detached/cross-origin frames, all relevant worker/worklet kinds, first-script and async/stale-owner cases, per-feature toggle/native controls in disposable profiles.
- Native protocol tests: malformed/untrusted inputs, unknown fields, forged/duplicate/stale revisions, output framing, helper crash, profile locks, container deletion, private-context retirement and launch-time unsupported policy. No credentials/seeds in logs or page-visible errors.
- Positive and negative privacy checks together: ordinary rendering, text edits, WebGL/WebGPU allocation/compute and audio/video calls work while prohibited host reads, foreign ownership and direct-network fallback fail. Test masked outputs against independent expected values; keep library warnings visible.
- Run pinned CreepJS/FingerprintJS locally on each engine, compare host-control data only in local fixtures, and check site/container separation. Warn about residual known limitations honestly rather than disable protections for a score.
- Re-run Gecko's complete maintained Node/Python suites and applicable runtime probes; Chromium's complete unit/C++/native suites; authenticated wire, route, lifecycle and packaging probes. A skip or missing build is incomplete acceptance.
- Independent reviews after each native group, then whole-change security/privacy, native host/IPC, and final installed-artifact review. Repair findings and rerun affected tests before shipping.
- Physical Mac camera/mic/screen tests require the user's native chooser/permission actions; never auto-grant, fake a successful capture or send media to third-party assessment sites as verification. Record unavailable physical checks as incomplete.
- Final installed app and DMG must contain exactly the reviewed/tested engines, manifests and configuration, with strict deep signature/resource checks. Keep a recoverable old app. Test both engines from the installed package, including normal startup with a previously used profile. Nothing is marked complete until every required parity group and real switching behavior pass.

## Implementation sequencing

First restore the native build volume and finish the existing identity/locale source build with runtime verification. In parallel with design, validate existing dual-engine baselines without changing release behavior. Then establish the full capability/snapshot and native owner transport, port the remaining native groups with their tests, prove the chosen presentation host, wire trusted identity selection to atomic real-engine routing, and run full review plus installed acceptance. Native source input hashes/build locks must include all pending reviewed changes; never mutate a source snapshot under an active build.

No product code, dependencies, installed engines or user settings were changed while writing this design.

## Builder review

Independent reviewer `chromium_parity_builder_check` found no additional consequential user questions beyond the pending presentation choice and disconnected build volume. Native signing availability and physical permission actions can be checked during execution. Baseline records are in `docs/dual-engine/parity-20261016/`; the five initial missing-native-identity failures are retained as baseline evidence. The recovered source-built identity app passes its current native tests; this does not complete the remaining groups.
