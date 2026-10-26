# Chromium native host checkpoint — macOS, 2026-10-16

This is an implementation checkpoint, **not a completed dual-engine release**.
The external APFS image is mounted at `/Volumes/CloakfoxChromiumBuild`. Its
existing identity framework completed the source build; the old pipeline stopped
during tests and left a stale `running` status. Fresh recovery checks use the
completed SDK without duplicating the source build or replacing the installed app.

## Verified scope

- Pinned identity patch and inherited native privacy hashes match the source tree.
- Native identity fixtures cover initial page script, frames, workers, navigation
  and fetch hints/languages, Intl/DST, individual toggles and native restoration.
- Gated CEF windowless mode renders owned local fixtures through both CPU and
  IOSurface callbacks. Paint memory is copied before callback return. Diagnostic
  replies expose bounded metadata, never a surface ID or pointer.
- Resize, keyboard, clicks and wheel input retain configuration revision checks.
  Unconfigured opens and invalid development flags fail before navigation.
- A review-reproduced popup defect shared opener state and created a separate
  native window. The gated mode now rejects these popups pending native host
  allocation. Existing windowed popup behavior retains its separate tests.
- Standalone Mach launch authenticates a known live spawned child using the
  kernel's audit trailer, then binds frame reception to its full audit token.
  Frame reception verifies tab token, configuration and viewport revisions,
  monotone sequence, surface format, dimensions, stride and allocation bounds.
  Owned snapshots survive sender mutation. Tests include real separate processes,
  wrong senders, malformed and oversized messages, stale/retired routes and dead
  receivers. A per-launch rendezvous name conveys no authentication authority.
- Versioned installed-Gecko158/candidate-Chromium coexistence passes four checks
  for independent persistent/private state and engine shutdown/restart behavior.

Current native-host results, hashes and logs are in `native-host-status.json`.
`native-foundation-status.json` is the earlier standalone foundation record; its
source paths, hashes and test count describe that older checkpoint. Earlier
`identity-baseline.log` records the negative result on the old framework.

## Remaining release work

Native CEF paint publication now reaches a privileged Gecko NSView through the
authenticated Mach boundary. The owned fixture verifies actual window identity,
IOSurface pixels, wrong-tab hiding, helper-death revocation and owner closure
during startup. A separate real native UI check typed `a` into Chromium and
received it at the owned fixture. This is gated development hosting, not automatic
UA-driven routing or production engine switching. The fixture preference defaults
to false; its helper still requires explicit probe and test-Keychain modes.

Independent source review found three host defects. Regressions first reproduced
HTTP-origin escapes (including redirects and worker requests), missed startup
cancellation and loss of the final paint under queue saturation. Native origin
checks, early lifecycle cancellation and one coalesced nonblocking frame retry
now pass those cases. The origin check covers the tested HTTP resource paths;
it is not WebSocket/preconnect/WebRTC policy parity. An additional parser test
reproduced oversized newline-terminated JSON bypassing the line-size guard; the
corrected parser passes six framing/bounds cases.

Native popup allocation, IME/accessibility/drag-drop, retina/video/occlusion
acceptance, normal navigation chrome and full same-window functionality remain
pending. Engine-family/version resolution and a distinct Default-container ID
mapping are tested schema2 primitives, not a production controller or v1 migration.

Full BrowserForge identity and schema2, Default-container mapping, display/fonts,
canonical rendering/GPU provenance, audio, clocks, devices, media permissions,
WebRTC/proxy policy and remaining browser/network policy are not completed in
Chromium. The companion still reports `privacyPatched:false`. Its implemented
feature tests cannot certify those missing groups. The installed Gecko app and
saved profiles have not been replaced or modified by this checkpoint.

The current independent review was read-only source inspection of the experimental
host and other pending changes. Its three concrete host findings were repaired
with failing-then-passing tests. It does not certify complete privacy parity.
Whole-port review, installed same-window tests and release packaging remain
required by the implementation plan.

One complete suite run encountered CEF's teardown watchdog after the WebGPU
assertions passed. Five instrumented repetitions and the final full run passed;
the earlier watchdog cause is unresolved and its failing log is retained. These
results must not be described as a permanent shutdown repair.

## Rejected launch experiment

Temporarily replacing the child's task bootstrap port reached the handshake but
stalled subsequent graphics initialization. A native sample traced the stall to
libxpc's cached bootstrap connection, initialized before `main()`. That approach
was removed. The current rendezvous keeps the normal system-service namespace;
it introduces no private libxpc reset or security-service port override.


## Native focus follow-up

The first-activation failure was reproduced with the uniquely identified native
test app: the Cocoa first responder returned to Gecko while DOM focus still
belonged to the Chromium browser. The new ChildView routing preserves that owned
viewport and declines unsupported browser modifiers. Two fresh rebuilt native
runs pass one click/one key, Cmd-L and address-bar text isolation. This is not
full keyboard/IME/accessibility acceptance.

Independent focus review found queued focus after tab changes and duplicate
native slots for one browser. Delivery and queued-write owner checks, startup
reservations, native duplicate rejection and ambiguity refusal repair those
cases. Native duplicate-owner RED/GREEN logs and the current passing host report
are retained. General engine routing and remaining native privacy groups are
still incomplete; the installed application has not changed.


## Viewport and presentation repairs

The Gecko-compositor prototype now publishes only authenticated, owned native
frames into the private chrome canvas. Real native typing and address-bar popup
visibility passed together with withheld-paint epoch clearing,2560px geometry,
ordinary resizing, wrong-tab hiding/restoration and helper-death revocation.
The previous native-view presentation remains a development comparison path;
its chrome-popup occlusion is not declared fixed.

Two reviewed rendering defects were reproduced before repair: retiring a viewport
epoch left old canvas pixels, and widths over2048 stretched the picture without
matching input coordinates. Retiring epochs now reset the owned bitmap. Both
engines and the host use matching rounded sizes through4096, bounded by the
existing64MiB transport. A real CEF test clicks at x2308 in CPU and IOSurface
modes. Dimensions beyond the supported bound fail rather than stretch.

The same authenticated local-fixture controller also supports explicit separate
Views windows, using the same immutable origin/configuration gate, original tab
ownership and process cleanup. A per-container settings preference defaults to
same-window and retains either choice. The settings UI explicitly states that
production Chromium switching is under development; a saved choice does not
make an incomplete engine available or trigger an unprotected fallback.

## Complete-policy contract boundary

`engines/shared/privacy_contract.json` names full required native group versions.
The native helper reports every complete group as0 and release eligibilityfalse;
its partial hook versions and legacy v1 protocol remain separate. The schema2
reference validator requires exact owner/revision bindings, all group versions
and trusted per-group validators returning exactlyTrue, in either presentation.
It validates one private immutable snapshot with cumulative byte/node/depth
budgets, including acknowledgements, and avoids exposing private diagnostics.
Independent review found mutable-data and late-resource-budget gaps; failing
regressions and the repaired21-test contract suite are retained here. No native
group or production route is declared implemented by these contract tests.

The subsequent BrowserForge CPU-count increment is being built into a distinct
candidate SDK/app. Existing4/8/16 defaults stay unchanged; new1–128 counts require
partial native identity version2. Its model/old-helper guards and source replay
passed, but native all-realm runtime verification is still pending. Consult the
external status file in native-host-status.json before treating that increment
as tested. Installed app and DMG remain unchanged.

## Native editing and BrowserForge CPU continuation

The rebuilt partial identity2 candidate passed CPU2/12/24 before the first page,
dedicated-worker, shared-worker and service-worker script. The initial full run
passed133/134 tests; the remaining failure was a stale Gecko settings/source
inventory, now refreshed. Full candidate acceptance is being rerun; the native
pipeline status remains authoritative. This does not complete BrowserForge OS
projection or any full native privacy group.

Bounded native editing keys now support arrow selection, Backspace/Delete, Tab,
Shift+Tab and Return. The expanded test reproduced and repaired missing newline
insertion separately. Invalid codes/types/mixed fields/stale revisions reject.
Actual CUA input in the Gecko compositor produced a,ac,a,ab after selection and
deletion; the same run passed epoch clearing,2560px alignment and owner retirement.
An independent real scroll moved the owned page900px. Separate-window startup and
owner-close retirement also passed with this candidate. Full IME, accessibility
and production engine switching remain unfinished. Installed app/DMG unchanged.

CPU2/keyboard candidate full acceptance subsequently passed135/135 engine tests
(104.696s, zero skips), CTest2/2, source/framework hashes, isolation, transport
and installed-Gecko coexistence. The preserved browserforge candidate and SDK
remain available while the following popup-rendering increment is developed.

The following owned select-widget popup increment passed137/137 engine tests
(112.114s, zero skips) and CTest2/2. CPU and IOSurface popup painting, selection,
container separation and resize retirement passed. A native receiver independently
verified popup pixels and removal. Actual CUA pointer input selected Second in
the Gecko-composited dropdown. Local generated video delivered both exact expected
colors and16 presented frames, then restored the original page after stopping.
These checks do not certify IME/accessibility or physical capture permissions.

## Native startup snapshot acceptance

The separate initial-snapshot framework/SDK candidate passed143/143 engine
tests (118.720s, zero skips), CTest2/2, source/framework hashes, isolation,
transport and installed-Gecko coexistence. Persistent and private owned contexts
attest effective settings before services initialize; first-script checks pass.
A new-SDK candidate refuses an older framework missing the required API symbol.
This is a partial version1 startup hook: complete native groups remain0.

The matching candidate also passed same-window epoch clearing, large viewport,
startup cancellation, duplicate-owner rejection, tab hide/restore, helper death
and generated-video checks; separate-window startup and owner-close retirement
passed. Reports retain exact binary paths and phase evidence. Installed app/DMG
remain unchanged; production engine switching and full privacy parity are pending.

## Fixture WebSocket boundary review

The independent85-file checkpoint review reproduced a P2: WebSockets bypassed
the HTTP-only fixture-origin restriction. The maintained regression reproduces
this from page, dedicated, shared and service workers; all requests use owned
loopback servers. A native owning-context gate is building in a separate retained
candidate, with full runtime acceptance pending. It must reject the other origin
while allowing a data frame from each same-origin socket; deny-all is insufficient.

The actual Gecko host now refuses the older helper in both presentation modes,
with zero fixture requests and no attached surface; helper descendants retire
within the existing bounded lifecycle deadline. Engine Node44/44, Gecko Node
305/305 and Python141/141 plus13 subtests passed. Fresh Gecko keyboard lifecycle
and DOM geometry runtime probes also passed. This remains development acceptance;
the installed browser and DMG are unchanged.

Fixture repair acceptance subsequently PASSED145/145 native engine tests
(113.961s, no skips), CTest2/2, isolation, transport and installed-Gecko coexistence.
Allowed sockets delivered data in page/all worker realms; forbidden handshakes
never reached their owned server. The exact candidate passed same-window
epoch/large viewport/video/cancellation/retirement checks and separate-window
startup/owner retirement. Strict native origin parsing remains intact; the one
initial runtime failure was corrected in trusted origin serialization only.
FrameworkSHA88502bc147486e07e88e6080a82ca6d95240ce656bac3b21c199e35e9908e79a.

The next owned-IME test is intentionally RED at missing native capability.
It is new pending work, outside this145-test accepted candidate. Full plan and
installed release remain incomplete.


Owned native IME/state increment:154 native engine tests and CTest2/2 pass; Gecko141+13subtests, engine Node61 and source replay6 also pass. Independent review findings on password/focus freshness and replacement ranges have automated regression repairs. See owned-ime-boundary-review-20261016.md and native-host-status.json. Same-window native metadata/lifecycle/video checks pass. Physical IME remains blocked by the locked Mac, cold-start acceptance is pending, and full privacy-group parity/general engine switching remain incomplete. Installed app/DMG unchanged.
