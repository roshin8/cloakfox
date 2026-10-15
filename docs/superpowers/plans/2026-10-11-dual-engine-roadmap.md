# Cloakfox Two-Engine Implementation Plan

> For agentic workers: execute each milestone with superpowers:executing-plans. This document is an architectural roadmap with a concrete first prototype; later milestones require implementation plans grounded in the prototype's findings. Checkboxes represent uncompleted work, not promised capabilities.

**Goal:** Keep the existing patched Gecko browser and add a real Chromium backend, with engine selection per container and equivalent privacy protections before general release.

**Architecture:** Initially, Cloakfox launches a separate CEF companion window through an authenticated local control channel. Gecko and Chromium own their processes, storage, page APIs and native networking. A common controller owns container intent and configuration; a shared tab interface is a subsequent milestone, subject to a successful rendering integration experiment.

**Tech stack:** Existing Firefox 157 fork; C++ CEF companion; source-built Chromium/CEF for native privacy patches; versioned JSON control messages; macOS arm64 first.

**Design basis:** User's two-engine requirement and `../specs/2026-10-11-network-identity-toggle.md`, especially its engine adapter boundary. CEF is a candidate to validate, not a final architecture decision.

## Constraints

- Preserve the current Gecko build, settings and container behavior.
- Engine choice is explicit: `gecko` or `chromium`. Editing a UA never changes engines silently.
- A Chromium identity uses its actual installed engine version. A requested unsupported identity is reported as unsupported.
- Never reuse Gecko network profile IDs, NSS settings or neqo configuration in Chromium.
- Never share cookie databases, cache directories, service workers, TLS sessions or connection pools between engines or containers.
- Existing page-level protections remain native where feasible; no MAIN-world injection architecture is introduced.
- Configuration and deterministic noise retain container plus top-level schemeful-site ownership.
- Privacy settings unsupported by a backend are visibly unsupported; they must not appear enabled.
- No website challenge bypass is an acceptance test. Use owned loopback fixtures and ordinary compatibility sites.

## Alternatives and decision

1. **CEF companion, then possible shared shell — recommended experiment.** Provides an embedding API and a small initial integration. Custom native protections still require maintaining Chromium source patches.
2. **Chromium browser fork as a companion.** Retains Chromium's complete browser application but makes a single interface harder. Choose this if CEF cannot supply required browser behavior or embedding proves costly.
3. **Raw Chromium Content API plus a new shell.** Offers control but puts more browser services and integration on us. Avoid initially.

The first experiment compares CEF against the requirements below. Do not build a new shared UI before that decision.

## Milestone 1: CEF feasibility prototype

**Deliverable:** A development-only Chromium companion with two isolated containers, launched from the command line, with one native privacy protection proven at runtime.

Proposed new files:

- `engines/chromium/CMakeLists.txt`: companion application build, pointing at an explicitly supplied CEF distribution.
- `engines/chromium/src/main_mac.mm`: application lifecycle and sandbox-compatible helper startup.
- `engines/chromium/src/browser_client.cc`: navigation, permission callbacks, window lifecycle and crash reporting.
- `engines/chromium/src/container_contexts.cc`: owns request contexts and validated per-container storage directories.
- `engines/chromium/src/control_channel.cc`: local authenticated message transport.
- `engines/chromium/patches/`: native privacy patch and ordered patch metadata.
- `engines/chromium/README.md`: pinned versions, build instructions and known limitations.
- `tests/engines/`: owned runtime fixtures and isolation/identity tests.

- [x] Record current Gecko baseline: working build, package, settings and representative isolation tests.
- [ ] Select and pin a supported CEF/Chromium release and matching build tools. Record exact versions and source revisions; preserve upstream licenses.
- [ ] Run an unmodified CEF sample on macOS arm64. Check sandbox, GPU/WebGL, WebGPU, audio/video permissions, downloads, popups and process crash recovery.
- [x] Build a minimal companion window with address entry, back/forward/reload and two selectable container contexts.
- [x] Give each container a separate request context and cache path under a dedicated prototype data root. Reject malformed IDs, path traversal and concurrent ownership of a profile directory.
- [x] Use a local fixture to write cookies, localStorage, IndexedDB, cache and a service worker in container A. Verify B cannot read them; restart and repeat. Check private contexts do not persist data.
- [ ] Inspect TLS/H2/H3 through owned server fixtures. Record actual Chromium behavior without routing requests through Gecko or modifying transport to resemble another engine.
- [ ] Build CEF from pinned source and implement one small native canvas privacy patch. Derive deterministic output from container and schemeful site; test reload stability, site/container separation and the disabled setting. Include workers/OffscreenCanvas where the chosen path applies.
- [ ] Inventory every existing Cloakfox protection and setting against Chromium implementation points. For each, record native hook, missing capability, worker coverage and test required.
- [ ] Write a findings report with measured build/update cost and browser feature gaps.

**Go/no-go:** Proceed with CEF only if the sandbox remains enabled, isolation tests pass, native privacy patching is maintainable, required browser functions work, and pages use Chromium's actual APIs/network stack. Otherwise evaluate the Chromium browser fork companion using the same tests.

## Milestone 2: Shared configuration and Gecko launcher

**Deliverable:** Select an experimental Chromium container from existing Cloakfox settings and open it in the companion window.

Existing integration points:

- `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`: existing persona ownership and generation.
- `additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs`: existing Gecko seed transport; preserve it.
- `additions/browser/components/cloakfox/CloakfoxNetworkProfiles.sys.mjs`: network capability boundary; register Chromium only once a real backend exists.
- `additions/browser/components/cloakfox/content/settings.js` and `settings.html`: explicit engine selector and supported settings.

Proposed modules: `CloakfoxEngineController.sys.mjs` for routing/lifecycle; a standalone shared schema under `engines/shared/` for backend-independent configuration.

- [ ] Define schema version 1: container ID, engine, configuration revision, persona seed, privacy options and backend capability report. Exclude Gecko preference names from the portable schema.
- [ ] Define commands `open`, `navigate`, `close`, `applyConfig`, `clearContainer` and events `ready`, `configApplied`, `navigation`, `crashed`, `error`. Include request IDs, reject unknown schema versions and acknowledge revisions.
- [ ] Authenticate the channel with a launch-specific secret over private local IPC. Restrict socket/file access; do not expose control commands to web content or a public HTTP port. Never log seeds or credentials.
- [ ] Apply a configuration snapshot before the first navigation. Reject stale updates and failed application instead of opening a page under unintended settings.
- [ ] Add the experimental engine selector. Disable Chromium selection when the companion is missing or incompatible; explain the reason without silently falling back to Gecko.
- [ ] Handle switching by closing and reopening affected tabs after confirmation when forms or active media would be lost. Do not transfer DOM state or submit forms automatically.
- [ ] Test helper death, launch failure, config mismatch, pending navigation, duplicate messages, profile locks and container deletion while tabs are open.

## Milestone 3: Chromium privacy parity

**Deliverable:** An audited capability matrix and native Chromium implementations for the required privacy settings.

- [ ] Split the inventory into focused patch groups: navigator/identity; screen/fonts; canvas/audio/WebGL/WebGPU; timezone/locale; WebRTC/media; clocks/scheduling; device APIs; storage/network ownership.
- [ ] Port each group against native Chromium/Blink/V8 hooks and browser-process services. Implement Firefox actor equivalents through Chromium-supported native mechanisms rather than copying privileged Firefox scripts.
- [ ] Keep UA, client hints, appVersion and engine capabilities coherent with the actual Chromium version. Preserve native networking by default.
- [ ] Carry site ownership through frames, workers, shared workers, service workers and redirects. Define and test ownership changes before applying deterministic noise.
- [ ] Test master disable, per-setting disable, restart persistence, new persona generation and the “clear overrides when generating” option in both UI and runtime.
- [ ] Require tests that observe actual page behavior, isolation and network traffic; metadata-only checks do not establish parity.
- [ ] Keep Chromium explicitly experimental until required protections pass. Unsupported settings remain disabled and described accurately.

## Milestone 4: One interface for both engines

**Deliverable:** A validated integration choice and, if viable, a common tab bar controlling both backends.

- [ ] Prototype displaying a sandboxed Chromium page surface inside the current Gecko application on macOS. Test focus, keyboard input, IME, clipboard, accessibility, scaling, resize, GPU composition, fullscreen and crash recovery.
- [ ] Compare native child views and off-screen composition. Measure performance and accessibility; do not select off-screen rendering solely because it is easy to demonstrate.
- [ ] If neither meets daily-use requirements, retain separate engine windows or design a new native shell with separate backend surfaces. This requires its own feasibility study for Gecko, which is not a drop-in desktop embedding library.
- [ ] After selecting the surface architecture, implement a backend contract for navigation, history, permissions, downloads, dialogs, fullscreen and tab lifecycle.
- [ ] Share bookmarks and application settings through a neutral store. Keep live browsing history/session state and website storage engine-owned; do not share password databases directly.
- [ ] Show the actual engine on each tab/container and preserve engine ownership through popups, restored sessions and external links.

## Milestone 5: Release and maintenance

- [ ] Bundle both engines and their helpers with licenses, enabled sandboxes, signed/notarized macOS packaging and reproducible version manifests.
- [ ] Establish separate upstream update pipelines and patch replay checks for Gecko and Chromium/CEF. Security updates must not wait for unrelated UI work.
- [ ] Validate upgrade/rollback compatibility without opening a newer engine's profile database in an older engine.
- [ ] Run the existing Gecko regression suite plus Chromium privacy/isolation probes against the packaged application.
- [ ] Measure package size, memory, idle processes, battery use and startup costs with one and both engines active. Launch only the engine needed.
- [ ] Publish the capability matrix and known differences; real Chromium is not a guarantee of equivalence with Google Chrome or acceptance by every website.

## Review focus

- Container and site state crossing backend boundaries: isolation must hold across restarts, workers and redirects.
- Missing or crashing helper: a tab must show an actionable error and never silently change engine.
- Settings changed during navigation: only acknowledged configuration may govern new documents.
- UI reporting a protection without implementation: capabilities must reflect runtime support.
- Updates and restores: engine/version ownership must survive packaging, profile migrations and rollback.

## Order and effort

Implement milestone 1 first, then 2 and 3 before undertaking the shared tab interface. Milestone 5 update infrastructure begins as soon as source patches exist.

For one engineer, a basic CEF window may take 1–2 weeks; the complete feasibility prototype with source builds, isolation and one native privacy patch is more realistically 2–4 weeks. A usable companion may take 2–3 months, and privacy parity plus a polished shared interface may take 4–8+ months overall. These are planning estimates, not delivery commitments; revise them after milestone 1.

No engines, dependencies, binaries or product code are changed by writing this plan.

## Execution status — 2026-10-13

Initial CEF companion implemented on `codex/dual-engine-prototype`; see
`../../dual-engine/cef-prototype-verification.md` and `../../../engines/chromium/README.md`.
The first milestone is partially complete. Binary build, real persistent/private
storage isolation, sandbox enforcement, permission denial, native API identity,
TCP/QUIC pre-certificate wire observations and crash recovery are proven. Native
privacy patches, full H2/H3 acceptance and remaining browser-feature checks are
open. Source-build prerequisites (full Xcode and sufficient APFS build storage)
block the required canvas patch; later milestones have not begun.

### Follow-up verification — 2026-10-15

Native UI verified against an owned loopback fixture: typed address navigation,
Back, Forward, Reload and close all worked; the launcher exited successfully.
Popup runtime tests confirm persistent container inheritance and private context
lifetime through opener/popup closure. These tests exercise existing behavior;
no Chromium runtime code changed in this follow-up. Page accessibility, downloads,
keyboard shortcuts and the source-native patch remain open.

The source preflight is still blocked: full Xcode absent, internal free capacity
below the 128 GiB build budget, external disk ExFAT. See the dated preflight
reports and `../../dual-engine/cef-prototype-verification.md`.
