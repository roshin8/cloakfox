# Independent Firefox 155 integration review

Reviewed the captured original-to-ported patch differences in `port-review.diff`
and the integrated Firefox source after all 75 patches, with particular attention
to HTTP/3, generated interfaces, build adaptation, and interactions among the
ported hooks. Read the earlier font, core, and geometry reviews and checked the
reported corrections in the integrated source. No patches or Firefox source
files were edited during this review.

**No additional concrete port-introduced blocker was found.** This is a source
and generated-interface review, not a successful full compilation or runtime
certification.

## HTTP/3 independent findings

The HTTP/3 port's constructor adaptation is consistent across the actual
generated FFI interface, both C++ wrappers, both Rust entry points, and the
internal constructor:

- `firefox-src/netwerk/protocol/http/Http3Session.cpp:192` and `:202` pass the
  profile after `fastPto`; the native path retains the file descriptor and
  `isOuterConnection` arguments after it.
- `firefox-src/netwerk/socket/neqo_glue/NeqoHttp3Conn.h:17` and `:31` preserve
  that ordering. In the generated
  `firefox-src/obj-aarch64-apple-darwin/netwerk/socket/neqo_glue/neqo_glue_ffi_generated.h:434`
  and `:452`, `fast_pto` and `fingerprint_profile` are both `uint32_t`, followed
  by the expected native-only arguments or result pointer. The C++ QPACK table
  size still widens from uint32_t to the generated uint64_t parameter; that is
  unchanged behavior.
- `firefox-src/netwerk/socket/neqo_glue/src/lib.rs:1089` and `:1138` forward
  these values to `NeqoHttp3Conn::new`; its existing fast-PTO configuration
  around `:507` remains separate from profile selection. The upstream
  congestion-control, slow-start, PMTUD and TLS parameter setup remains intact.
- The `Http3Parameters` QPACK setters update the current `qpack::Settings`
  object. `firefox-src/third_party/rust/neqo-http3/src/connection.rs:313`
  passes that same object to the actual decoder; the decoder at
  `firefox-src/third_party/rust/neqo-qpack/src/decoder.rs:43` reads its blocked
  stream limit. Thus the profile-specific minimum of 100 is not merely an
  advertised SETTINGS change: the decoder receives the raised capacity.
- Profile zero and unknown values retain Firefox's SETTINGS arm, including
  upstream feature values. Alternate profile ordering and constants match the
  captured original patch. Current connection feature negotiation and remote
  SETTINGS/QPACK handling were inspected for interactions with that conversion.
- Independently calculated SHA-256 for **all 61 files** in the integrated
  `neqo-http3/.cargo-checksum.json`: **zero mismatches**. The new upstream file
  inventory is retained.

The Safari fixed table-capacity advertisement and sparse alternate-profile
feature advertisements are inherited from the captured original patch. They
remain runtime risks, as described in `http3-port.md`, rather than newly
introduced port defects. This review does not establish compatibility of those
profiles with QPACK-heavy responses, WebTransport, CONNECT-UDP or resumption.

## Generated interfaces and integrated hooks

- The actual generated `dom/bindings/WindowBinding.cpp` dispatches screen
  setters at lines 9910/9954 and font/audio seed setters at 10146/10190 with
  arguments matching `nsGlobalWindowInner.h`. Generated manager headers and
  WebIDL gate references are present, rather than relying only on IDL text.
- The generated `dom/bindings/ElementBinding.cpp:5605` alias supplies its
  subject principal to `GetOpenOrClosedShadowRoot`, matching
  `firefox-src/dom/base/Element.h:1737`. The port's new
  `NeedsSubjectPrincipal` annotation is therefore reflected in generated code.
- The generated `dom/bindings/RangeBinding.cpp:1346` and `:1422` call the
  inherited `GetClientRects` and `GetBoundingClientRect` APIs, whose noise
  hooks now reside in `AbstractRange.cpp`. The migration does not require a
  separate Range binding override.
- The generated `ipc/ipdl/PContentParent.cpp:15684` and `:15737` dispatch the
  storage messages with arguments matching the added `ContentParent`
  receivers. Both synchronous messages have declarations and allowlist
  entries in the integrated source.
- The async WebGL correction captures the resolved scalar seed before IPC,
  applies the helper once to the copied RGBA surface, and retains the existing
  swizzle/flip and error paths. Its synchronous sibling retains the previous
  lookup behavior. The CI unit-test job at `.github/workflows/build.yml:506`
  explicitly invokes the new helper/source regression test. The test models
  the callback contract and compiles extracted helpers; it does not prove
  browser capture-stream output or per-domain isolation.
- The letterboxing getter migration uses the upstream helper that performs
  `Top()` internally (`BrowsingContext.h:724`). Screen/orientation/media
  hooks agree with the updated `nsPresContext` writer, and the content-only
  gate is retained.

Generated-file paths in this section are relative to
`firefox-src/obj-aarch64-apple-darwin/`. They were inspected as build artifacts,
not manually edited.

## Build/configuration review and limits

The optional asset-catalog check resolves the configured branding directory
under the source root and is consumed by the current `MacOSBundle` extra-file
list. Other icon and updater entries remain intact. The current configured
tree reports `MOZ_BRANDING_DIRECTORY=browser/branding/cloakfox` and a present
catalog; therefore that build does not independently exercise the absent-file
branch. The package manifest's unconditional catalog entry is inherited and
already documented in the core review.

The integrated namespace/include additions, moved font-shaping signatures,
current relevant-global/storage ownership APIs, and retained upstream return
paths in the changed WebGL and FontFace methods revealed no additional
signature or duplicated-hook issue. The corrected Mozilla native-manifest
branch forces legacy-home lookup, matching the other native-manifest branch.

The parent task owns the ongoing compiler/build work. This review did not run
another build concurrently and makes no claim that Gecko linking, platform
packaging or live fingerprint probes have passed. Complete compilation and
browser tests remain necessary, especially asynchronous capture output and
both HTTP/3 I/O modes. The earlier documented container-only C++ seed scope
and synchronous WebGL destination-padding behavior were not introduced by
this version port and are not additional port blockers.

## Follow-up: compiler-discovered OffscreenCanvas accessor migration

The subsequent compiler pass found four `OffscreenCanvas::GetOwnerGlobal()`
calls that the initial source review did not identify. Two were in initially
failing patches, while the two calls in `canvas-spoofing.patch` had applied
without rejects. Clean patch application was therefore insufficient
to establish API compatibility. The integrating task corrected all four calls
and reports a successful 75-patch application in `ported-pass-4`.

**Scoped re-review: all four replacements with `GetRelevantGlobal()` are
correct; no remaining instance of this removed API was found in the patch
stack or existing patched source files.**

| Corrected patch location | Integrated source location | Receiver and behavior |
| --- | --- | --- |
| `anti-font-fingerprinting.patch:541` | `firefox-src/dom/canvas/OffscreenCanvas.cpp:660` | `this` is `OffscreenCanvas`; its font visibility `GetDocument()` retains the main-thread guard, window query and null fallback. |
| `webgl-spoofing.patch:259` | `firefox-src/dom/canvas/ClientWebGLContext.cpp:807` | `mOffscreenCanvas` is an `OffscreenCanvas`; the WebGL container-ID helper retains window/BrowsingContext and worker-origin-attribute branches. |
| `canvas-spoofing.patch:230` | `firefox-src/dom/canvas/CanvasRenderingContext2D.cpp:2317` | The same OffscreenCanvas receiver supplies the global for encoded-image noise identity. |
| `canvas-spoofing.patch:264` | `firefox-src/dom/canvas/CanvasRenderingContext2D.cpp:6815` | The same receiver supplies the global for ImageData noise identity; window and worker fallbacks are unchanged. |

`OffscreenCanvas.h:64` inherits `DOMEventTargetHelper`, whose current
`GetRelevantGlobal()` override at `dom/events/DOMEventTargetHelper.h:72`
forwards to `GlobalTeardownObserver::GetRelevantGlobal()` and returns
`nsIGlobalObject*`. `OffscreenCanvas.h:86` already uses this accessor for
`GetParentObject()`. The replacements therefore retain the expected type and
object ownership semantics, and match adjacent upstream OffscreenCanvas calls.

An explicit scan of all **75 patch files** found **zero added
`GetOwnerGlobal` references**. A second scan of the existing integrated source
files targeted by their patch headers found **zero remaining references**.
Checked the remaining added `GetOwnerWindow()` and `GetParentObject()` calls
against actual receiver declarations instead of mechanically renaming them:

- `SpeechSynthesis`, `Clipboard` and `FontFaceSet` inherit
  `DOMEventTargetHelper`/`GlobalTeardownObserver`; the latter still declares
  `GetOwnerWindow()` at `dom/base/GlobalTeardownObserver.h:23`.
- `AnalyserNode` inherits `AudioNode`, whose `GetParentObject()` returns
  `AudioContext*` (`AudioNode.h:76`). `AudioContext::GetParentObject()` still
  returns `nsIGlobalObject*` (`AudioContext.h:147`).
- `AudioBuffer::GetParentObject()` still returns `nsPIDOMWindowInner*`
  (`AudioBuffer.h:67`). Its added callers use that type.

No likely next compile error from this same accessor migration was identified.
This follow-up is limited to source/type verification; the integrating task's
resumed build must establish compilation success.

## Follow-up: placement audit of originally clean patches

After the compiler exposed misplaced media-capabilities hunks, independently
audited the other originally clean patches for the same failure mode. Selected
the 47 originally applied entries from `155.0.1/results.json`, excluding the
media-capabilities patch being repaired and the canvas patch already reviewed
above. This left **45 patches**.

For each existing target file, compared an independent
`git merge-file -p before-155.0.1 before-146.0.1 after-146.0.1` result with its
captured `after-155.0.1` snapshot under the scratch `steps/` directory:

- **101 existing-file merges matched byte for byte**; no successful merge
  produced a different placement from patch application.
- **Four candidates conflicted** and were inspected in the current integrated
  source. `browser-init.patch` keeps the new Picture-in-Picture block outside
  Cloakfox startup logic; `fingerprint-injection.patch` keeps the include path
  at build-file top level after the new custom-icon loop;
  `navigator-spoofing.patch` adds declarations beside, rather than replacing,
  the new shared-worker declarations; `worker-container-identity.patch`
  warms the cache before registration and retains the upstream remote-debugger
  endpoint setup. None revealed misplaced integrated code.
- **Seven new files** had no ancestor to merge; their contents were identical
  in the Firefox 146 and Firefox 155 per-step snapshots.
- As a positive control, the known-bad original
  `media-capabilities-spoofing.patch` produced **two three-way conflicts** and
  differed from its originally applied output. This independent comparison
  does detect the observed ambiguous-context failure.

Focused reads also checked method placement and return types for window and
worker navigator getters; AudioContext output latency and maximum channel
count; Cubeb preferred sample rate; speech voice enumeration and registry
speech handling; media feature getters, exposed-device filtering and MSE type
support; SVG geometry/text lengths; and timezone/Math initialization within
`WorkerPrivate::GetOrCreateGlobalScope`. No additional concrete wrong-method
insertion or incompatible return logic was found. Three-way agreement is
additional evidence, not proof of semantic compatibility or full compilation.

## Scoped re-review: media-capabilities placement repair

**The current repair closes the observed wrong-placement failure.** The original
generic-context hunks had both landed inside `EncodingInfo`, leaving decoding
unprotected and referring to the wrong promise variable. Re-read the regenerated
patch and current `dom/media/mediacapabilities/MediaCapabilities.cpp`:

- There is exactly one decoding hook at source line **814**, inside
  `MediaCapabilities::DecodingInfo` beginning at **763**. It follows promise
  creation, the WebRTC availability gate, configuration validation, and the
  key-system worker/non-secure-context rejection paths. It constructs
  `MediaCapabilitiesDecodingInfo`, initializes all three booleans and nullable
  `keySystemAccess`, resolves the method's `promise`, and returns it before
  `CreateMediaCapabilitiesDecodingInfo` at **825**.
- There is exactly one encoding hook at **1324**, inside
  `MediaCapabilities::EncodingInfo` beginning at **1298**. It follows the
  WebRTC and configuration validation gates, constructs `MediaCapabilitiesInfo`,
  and consistently resolves/returns **`encodePromise`**. That result type
  matches the current `MediaCapabilities.webidl` encoding return dictionary.
- With spoofing disabled, both hooks fall through to the existing native
  implementation. The decoding dictionary is no longer constructed inside
  encoding, and no decoding hook references the encoding promise or vice versa.

The integrating task reports the resumed build has passed MediaCapabilities
and entered remaining DOM compilation. This scoped review independently
verified source placement, dictionaries and promise usage; it did not run a
second compiler or runtime MediaCapabilities probe. Full build and runtime
validation remain owned by the integrating task.

## Follow-up: explicit window inline definitions and successful build

**The 15 `nsPIDOMWindowInlines.h` additions are correct and minimal.** Firefox
155 declares `GetBrowsingContext()` inline in `dom/base/nsPIDOMWindow.h:414`
and `:899`, but supplies its definitions in
`dom/base/nsPIDOMWindowInlines.h:71` and `:76`. Translation units calling those
methods must see those definitions; relying on a declaration or another member
of a unified compilation unit can leave unresolved references at XUL linking.

Inspected the added include in each affected translation unit:

- `dom/base/`: AudioFingerprintManager, CanvasFingerprintManager,
  CloakConfigOverlay, FontListManager, FontSpacingSeedManager, NavigatorManager,
  ScreenDimensionManager, SpeechVoicesManager, TimezoneManager,
  WebGLParamsManager and WebRTCIPManager.
- `gfx/src/nsFontMetrics.cpp`, `gfx/thebes/gfxTextRun.cpp`,
  `layout/generic/MathMLTextRunFactory.cpp` and `layout/mathml/nsMathMLChar.cpp`.

Every file contains a window `GetBrowsingContext()` call and exactly one
explicit include at file scope. Comparing each file in `ported-pass-5` with
`ported-pass-7` showed that removing just the newly added include restores the
earlier file byte for byte. There are no accompanying changes to control flow,
identity resolution, declarations or implementations. The header is guarded
and provides the existing inline bodies; the fix adds no replacement function
or platform-specific behavior.

Independently verified the current patch inputs against the SHA-256 values in
`ported-pass-7/results.json`: **all 75 match**. Parsed their target headers and
compared all **171 integrated target files** with the verified pass-7 source:
**zero missing files and zero byte differences**, including all 15 affected
translation units. The pass-7 manifest records **75 successful patches, zero
rejected hunks and zero ignored hunks**. This comparison was taken before the
separately assigned runtime randomization investigation changed any inputs.

The latest `build.log` now ends with **“Your build was successful!”** after
the integrating task's successful build completion. This supersedes the
earlier pending-compilation statements in this report. The one reported
warning concerns an unused `NavigatorManager.cpp` helper, not an unresolved
window accessor. No further source/input divergence or defect was found in
this scoped review. Browser runtime findings and the ongoing canvas
randomization investigation are outside this review's scope.

## Scoped review: letterboxing media-query invalidation

Reviewed the new `BrowsingContext::DidSet` overload for
`InnerSizeSpoofedForRFP` in `cloakfox-letterboxing.patch` and the integrated
source. **No source-level blocker found; the change addresses the missing
invalidation mechanism observed by the runtime probe.** A rebuild and rerun
are still required to establish that the observed failure is resolved.

`runtime-letterboxing.log` shows correct top-level geometry in three size
buckets, followed by a fixed-size iframe retaining cached device-width
`matchMedia`/CSS results `[True, "1"]` after the top viewport changed. The
iframe's own layout size does not need to change when its spoofed device size
changes, so normal iframe viewport invalidation does not cover this case.

- The field's existing `CanSet` rule remains restricted to top-level browsing
  contexts (`BrowsingContext.h:1565`). The new callback at
  `BrowsingContext.cpp:3512` returns immediately when the value is unchanged.
- `WalkPresContexts` at `BrowsingContext.cpp:3137` traverses the browsing-context
  subtree and calls the callback only for locally available docshells and
  presentation contexts. The per-document `UseCloakfoxLetterboxing` predicate
  excludes chrome/system documents and disabled Cloakfox letterboxing. Normal
  upstream RFP documents without that predicate do not gain extra invalidation.
- `SystemMetricsChange` is appropriate for spoofed device dimensions. The
  device-width, device-height and device-aspect-ratio feature declarations
  lack Servo's `VIEWPORT_DEPENDENT` flag. This follows the existing
  `TouchEventsOverrideInternal` callback's system-metric invalidation pattern
  at `BrowsingContext.cpp:3455`.
- `MediaFeatureValuesChanged` (`nsPresContext.cpp:2010`) schedules style and
  media-query-list updates and merges pending changes. It does not immediately
  perform a layout flush or write `InnerSizeSpoofedForRFP`. The callback itself
  makes no field assignment and sends no IPC, so there is no direct callback
  recursion or IPC feedback loop. Later layout changes may publish another
  size through the existing writer; unchanged-size notifications are filtered.
- `JustThisDocument` is correct because the explicit walk already visits
  descendants. It prevents redundant recursive document propagation and does
  not force iframe dimensions to equal the top viewport. It also avoids
  changing image-document propagation beyond the scoped browsing-context
  behavior.
- `SyncedContextInlines.h:206` swaps in the new field value before invoking
  `DidSet`. Both local commits and received IPC transactions reach that path;
  parent receipt forwards to the other participating content processes. Each
  iframe process can therefore invalidate its local presentation contexts
  after receiving the replicated top-level size. Existing epoch/discarded
  context handling is unchanged. Initial context construction without a
  callback has no previously cached media result to invalidate.

The captured original `original-patches/cloakfox-letterboxing.patch` has no
`BrowsingContext.cpp` or `.h` hunks. This is a newly added runtime correction
for the existing captured resize probe; its absence may also affect the
Firefox 146 input, and this review does not establish that Firefox 155 alone
introduced the gap. The implementation agent reports deriving the two added
baseline files from the worktree's Firefox 155 source, which earlier captured
patches did not modify, and copying no concurrent original-checkout edits.
The fix therefore belongs to the explicitly requested runtime validation
scope, with that provenance recorded rather than attributed solely to an
upstream API rename. No canvas changes were reviewed in this follow-up.

## Scoped review: Firefox 155 canvas extraction policy

Reviewed the final stacked `CanvasUtils.cpp`, its call sites, the configured
seed path and `runtime-canvas-randomization-ab.json`. The A/B evidence supports
replacing native session randomization when Cloakfox has an effective canvas
seed: identical seeded readPixels results accompany varying encoded exports
with efficient baseline randomization enabled, while disabling that baseline
makes both exports repeat. The helper is narrowly placed after native access
checks and before the two native randomization choices.

- Both HTML and OffscreenCanvas preserve `IsUnrestrictedPrincipal` and then
  `IsImageExtractionAllowed`/`Placeholder` in their original order. The new
  override cannot turn an upstream permission-gate denial into real pixels.
  Existing caller-side write-only/taint checks also remain outside and before
  extraction. As before, the native permission gate consults explicit canvas
  permission only when the corresponding RFP gating targets require it.
- The helper reads the supplied principal's userContextId. HTML export passes
  its subject principal; Offscreen export passes its context principal; WebGL
  readback uses its canvas/global principal. This follows the existing native
  extraction identity. Ordinary content cannot access another container's
  canvas through a same-origin reference, because container origin attributes
  remain part of the principal security boundary.
- Disabled Cloakfox short-circuits before MaskConfig. Missing or invalid
  unsigned seed values retain native policy (unless MaskConfig's existing
  environment fallback supplies an effective seed). Explicit zero is present,
  so it deliberately selects the no-noise path. The final, later
  `unified-maskconfig.patch` implementation of `CanvasFingerprintManager::GetSeed`
  does pass its explicit container ID and preserves zero. An initial reviewer
  concern based on the earlier manager-creation patch was withdrawn after
  checking that final stacked implementation.
- `cloakfox.enabled` is a RelaxedAtomicBool mirror. The new helper reads only
  principal attributes and the existing MaskConfig storage path; it adds no
  worker access to window/document APIs. Storage cache reads are mutex-guarded
  and main-thread-only IPC fallback remains guarded.

**Integration finding corrected; runtime verification pending:** two WebGL noise readers
previously omitted the container argument: `ClientWebGLContext::GetImageBuffer` and
`ClientWebGLContext::DoReadPixels`, both added by `webgl-readback-noise.patch`.
On a nondefault worker their context-blind MaskConfig calls resolve container
zero, while the new extraction gate sees the worker's actual principal seed.
The result can suppress native export randomization and then apply container
zero's noise or no noise. Forwarding the existing `GetUserContextId()` at
both reads is the minimal correction. The async readback reader already
passes that ID. A scoped recheck confirms both calls now pass
`GetUserContextId()` in `webgl-readback-noise.patch` and the final
`ClientWebGLContext.cpp` (lines 1460 and 5775). The source-level blocker is
resolved. The implementation agent reports all 75 patches passing in
`ported-pass-10`; the rebuild and queued worker probe still need to establish
runtime success.

Added `probe_worker_canvas.py` as an independent regression probe. It uses a
local HTTP page and disposable profile with fixed seeds for default and three
nondefault containers (including explicit zero), preserving the valid font
configuration that prevents automatic persona regeneration. It compares
window versus dedicated-worker OffscreenCanvas WebGL pixels/encoded blobs
and 2D pixels/encoded blobs, repeats across reloads, and checks distinct
container seeds remain distinct. Drawing is font-free to isolate pixel noise.
Python and all three embedded JavaScript fragments pass syntax checks. The
two extraction-policy unit tests pass. The worker probe has not yet run in
this review because the browser build is active; source inspection and these
unit checks do not establish browser runtime success or native-denial UI
behavior.

## Runtime follow-up: cpp-first worker cache warming

`worker-canvas-recheck.log` showed every worker reading unnoised pixels,
including the default container, while the windows correctly differed by
seed. The worker exports retained native randomization. This ruled out only
a nondefault-container ID problem: the worker had no effective cpp-first
canvas configuration at all.

Final-source inspection identified the cache bypass. WorkerPrivate's existing
main-thread constructor calls `RoverfoxStorageManager::GetString` to warm
`cloak_cfg_<id>`. That function first calls `TryGetCppFirstPref`, which returned
a successful `cloakfox.s.*` preference or parent IPC value immediately,
without filling the cache. Its early return bypassed the later legacy
`roverfox.s.*` cache warming. The same cpp-first helper attempted Preferences
reads off-thread, and workers could not use its correctly main-thread-guarded
IPC fallback. The earlier review's statement about guarded storage reads was
therefore incomplete: the legacy GetString path was guarded, but its
cpp-first fast path was not.

Corrected `cpp-first-pref-reader.patch` and the integrated
`RoverfoxStorageManager.cpp` helper. Worker calls now read only the existing
mutex-protected cache under the full cpp-first preference name. Main-thread
calls preserve preference/parent-IPC priority and refresh that namespace's
cache before returning. A missing value removes the cached snapshot on the
next main-thread lookup. The explicit main-thread IPC guard remains intact.
WorkerPrivate's existing warm-up therefore reaches the correct cache without
adding a new worker-to-main-thread protocol or changing seed generation.
Workers use the snapshot warmed/refreshed by main-thread reads, consistent
with the existing worker storage design.

The new `test_cpp_first_worker_cache.py` compiles the actual helper extracted
from its patch with storage/thread stubs. Before the correction it fails at
the worker's attempted Preferences read; after the correction it passes.
It covers parent-IPC warm-up for two containers including a zero seed,
worker cache hits and misses without Preferences/IPC calls, later preference
refresh, removal, and container isolation. Browser rebuild and rerunning the
worker canvas probe remain necessary to verify the observed runtime failure
is resolved. This follow-up modified no other native source or patch.

## Scoped review: Firefox 155 actor registration and seed startup

No blocker found in the two scoped compatibility corrections. SeedSync's
`ContextualIdentityService` import now uses
`moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs`,
matching Firefox 155's own `browser.js` import and that module's
`MOZ_SRC_FILES` packaging declaration. The additions and integrated source
copies are byte-identical. `seed-startup-before-fix.json` records the old
resource-URI load failure with no seed preferences or shared data;
`seed-startup-diagnostic.json` records the successful original module exports,
15 math/keyboard/timing seed keys for containers 0–4, their shared-data
snapshot, and a generated base64 seed length of 44. This supports the stated
startup fix without claiming each actor's complete runtime behavior.

All 12 Cloakfox entries in `cpp-first-actors-registration.patch` now explicitly
set `safeForUntrustedWebProcess: true`. The final actor registry contains
those flags, and Firefox 155's `JSActorService` checks this opt-in when
matching untrusted web processes. Existing http/https/file matches,
all-frame scope and DOMDocElementInserted events are preserved. Each of the
12 corresponding parent modules exports only an empty JSWindowActorParent
subclass, with no parent message handler or added privileged operation; the
additions and integrated copies match. This is an appropriate opt-in for the
existing child-side spoofers, rather than a bypass of the process check for
unrelated actors. Review was read-only apart from this report, used no
browser or escalated tools, and did not cover the separate AboutDialog audit.

## Final runtime verification and About dialog review

The final Firefox 155 macOS arm64 run passes all 39 actor signals, including
the three seed-startup checks that previously failed. The window/worker canvas
probe also passes across four containers after the cache correction above.
All twelve selected fingerprint probes and four HTTP/3 preference tests pass.

An additional About dialog smoke test exposed Firefox 155's chrome-document
CSP rejecting its inline `onload` and close `oncommand` handlers (captured in
`about-dialog-before-csp-fix.log`). The additions now use the current
AppConstants ES module and external load/command listeners; version display
uses `textContent`. A focused browser rerun verifies the correct version,
no dialog console errors, and successful close-command handling. Independent
read-only review found no blocker in the lifecycle, handler wiring, module
import, or probe. The test dispatches `command` directly rather than testing
physical Escape-key routing. This brings the selected live probe total to 13.

The final build passes, all 75 patches apply in `ported-pass-14`, and all 174
patched targets plus three changed additions match the integrated source.
The 23 Node tests, probe-scoring self-test, and five new compiled regression
tests pass. No Linux/Windows build, live QUIC SETTINGS capture, full async
capture-stream rendering test, or per-domain isolation proof is claimed.

## Reconciliation of newer letterboxing changes

The original checkout's three post-snapshot files have now been reconciled in
this worktree. Native browser UI screen and available-screen rectangles bypass
persona overrides; CSS device size and resolution retain native behavior for
chrome documents. Firefox 155 uses `GetOuter()` with `nsGlobalWindowOuter::Cast`
for the screen guard because the older `GetOwnerWindow()` helper is unavailable.
The shared DeviceType/DeviceAngle helpers now cover content letterboxing, so
legacy `screen.mozOrientation` agrees with modern orientation; System callers
used by orientation update/locking internals remain native.

The existing exact preference callback list now includes both `cloakfox.enabled`
and `privacy.resistFingerprinting.letterboxing`. Their callback refreshes the
stored top size with Firefox 155's UpdateInnerSizeSpoofedForRFP API and invalidates
each document's device-size/resolution media queries. This covers fixed-size
iframes on opt-out or unchanged viewport dimensions. The prior resize-driven
BrowsingContext invalidation remains intact. Independent read-only review found
no blocker in these guards, shared helpers, or callback registration lifecycle.

The expanded original probe adds native chrome geometry, legacy orientation,
multiple-container, and cached iframe CSS toggle checks. Its new-tab wait now
requires both the destination URL and readyState complete, avoiding a read of
initial about:blank. The pre-fix run recorded mismatched chrome screen geometry,
portrait legacy orientation, and stale cached iframe CSS on both opt-out paths
(`letterboxing-expanded-before.log`). After rebuilding, all expanded checks
pass (`final-letterboxing.log`). The full stack applies in `ported-pass-15` with
no failures, and the incremental macOS arm64 build succeeds with zero warnings.

The About dialog, navigator-coherence and additional-vector probes also pass
on the reconciled build. Source verification confirms all 174 patched targets
and three changed additions match fresh stack output. Patch count remains 75,
with 37 changed relative to the original captured input.
