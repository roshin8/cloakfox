# Cloakfox native browser compatibility design

**Date:** 2026-10-10
**Status:** Approved by the user on 2026-10-10; screen-management scope revised by the user in the same session; implementation planning

## Requested outcome

Use the latest Cloakfox source and DMG to repair the crashed Cloudflare widget
and support TestDome in Cloakfox. Keep the default browser identity Firefox,
but expose the optional screen-management API only when the owning document
uses a desktop Chrome/Chromium/Edge identity. The user revised the earlier
Firefox-eligible proposal to require a separate toggle and an editable site
allowlist. The user additionally requires a configurable virtual screen count
and the allowlist beside the toggle. Screen count defaults to one and is
selectable from 1–8; display properties use existing persona overrides. General UA/header refactoring is outside this
revision; the screen feature gets its own Settings controls.

## Baseline and reproduced evidence

Investigation uses commit `c536c1ebda`, with a clean working tree before these
documentation edits, and
`cloakfox-146.0.1-beta.25-appearance-recovery-20261010.dmg`.
Build ID is `20261010162253`. Its executable's SHA-256 is
`54ee08c14f7f59780d83dfe753f793cfe9f2e3d337b68308874874a9db0923ba`,
matching `/Applications/Cloakfox.app`. The installed application and active
user profile are not changed by this investigation.

The latest signed DMG reproduces the CapitalOne Cloudflare widget's red
Firefox crashed-frame icon. The native log records content-process signal 11.
LLDB with the matching unstripped XUL symbols reports:

```
EXC_BAD_ACCESS, address 0x8
nsWrapperCache::GetWrapperMaybeDead(this=nullptr)
GetOrCreateDOMReflector<mozilla::webgpu::Instance>(value=nullptr)
Navigator_Binding::get_gpu
```

`Navigator::Gpu()` in `navigator-extra-spoofing.patch` deliberately returns
null when `navigator:webgpu:disabled` is true. `WebGPU.webidl` declares a
non-nullable `GPU gpu`, so the generated getter wraps the null pointer without
checking it. The existing WebGPU actor hides the page getter, but an unpatched
blank iframe can still reach this native path. A local HTTP page with a blank
iframe reproduces signal 11 under the master-on default. The master-off control
reads a GPU object safely. On the live link, the isolated master-off Firefox
control clears the widget automatically and reaches the CodeSignal login page.
No CAPTCHA was clicked and no login or assessment was started.

TestDome's inspected proctoring bundle checks capability presence:
`getDisplayMedia`, `getUserMedia`, `OffscreenCanvas`, and `getScreenDetails`.
Its screen initializer awaits `getScreenDetails()` and installs a
`screenschange` listener. No Chrome UA/Client Hints condition occurs in these
inspected support predicates. This establishes the relevant capability gate,
not every possible application check.

Local probes against the DMG, with Firefox identity and the master enabled,
confirm native capture methods, OffscreenCanvas, VideoEncoder, and MediaRecorder
are present. The confirmed absent method is `getScreenDetails`.
TestDome's actual codec profiles include a `no-preference` VP8 fallback.
At its configured 1920x1080 screen and 640x360 webcam sizes at 15 fps,
VideoEncoder and MediaRecorder agree on VP8/WebM, with Opus for webcam audio.
Hardware H.264 success is not assumed.

A headful local probe records synthetic canvas video and synthetic audio using
these settings: screen WebM is 4,098 bytes and webcam VP8/Opus WebM is 6,503
bytes, both with valid EBML headers. The first headless recording fixture timed
out; the successful headful fixture permits autoplay solely in its disposable
profile to run the synthetic audio source. These results establish local
recording, not OS screen capture or real webcam/audio-device delivery.

Diagnostic scripts, local results, native logs, and the symbolicated crash
stack are stored under `/tmp/cloakfox-compat-20261010/`. These are temporary
investigation artifacts; a permanent regression probe must preserve the minimal
local reproducer before implementation is considered complete.

## Cloudflare crash repair

Make the native WebIDL contract match the existing disabled-WebGPU return:
declare `GPU? gpu` in `WebGPU.webidl`. Nullable attributes make Gecko generate
calls to `GetGpu()` rather than `Gpu()`, so rename the matching declaration and
definition in both Navigator and WorkerNavigator without changing their bodies.
This adds the generated null check before DOM wrapping, preserving the
intentional no-GPU result. Keep the native
getter, `[SameObject]`, secure-context restriction, and existing actor behavior.
Master-off and WebGPU-enabled cases still return their native GPU object.

Deliver this as an ordered `cloakfox-webgpu-null-safety.patch`, after
`navigator-extra-spoofing.patch`. The shared mixin also supplies worker bindings;
verify their enabled native-object behavior remains unchanged. This repair does
not grant GPU access or change Cloudflare challenge state, tokens, scripts,
network identity, or verification decisions.

The local crash regression exercises the raw getter in normal, blank,
srcdoc, and navigated frames under master-on/off. It must detect content-process
death even if WebDriver returns a null result instead of raising an exception.
Check native null results when disabled and valid object identity when enabled.
The live verification target is a functioning widget with no process crash;
challenge acceptance remains the service's decision.

## Native screen compatibility

Add native `ScreenDetailed` and `ScreenDetails` C++ classes and WebIDL bindings,
`Window.getScreenDetails()` returning a Promise, and `Screen.isExtended`.
Enable these surfaces only when all four conditions hold: the master is on,
the separate `cloakfox.compat.screen_management` toggle is on, the owning
document has a desktop Chrome/Chromium/Edge UA, and its exact HTTPS principal
origin is in `cloakfox.compat.screen_management.origins`. The toggle defaults
to false. The origins preference is a JSON array, initially
`["https://app.testdome.com"]`, editable through Settings. Keep the toggle,
**Virtual screen count** dropdown (1–8) and exact-origin editor together in one
Settings group; the count and allowlist controls sit immediately beside/below
the toggle, with Save/Reset actions and reload guidance.
`cloakfox.compat.screen_management.screen_count` is a profile-wide integer
preference, default 1. Wrong-type/out-of-range values use deterministic count 1.
New inner windows snapshot the validated count; reload affected pages after
changing it. Existing details arrays remain stable for their document lifetime.

Firefox/Safari identities, mobile/Android/iOS identities, unlisted origins,
insecure contexts, opaque principals, workers, master-off and feature-off
retain the existing absent screen-management surface. An eligible same-origin
child is allowed; an embedded child must independently meet the same UA/origin
checks. Do not enable by trusting a top-level URL string.

Allowlist entries are canonical exact HTTPS origins, including a nondefault
port when explicitly listed. No wildcards, subdomain inheritance, paths,
queries, fragments or credentials. Settings displays one origin per line and
validates a complete draft before saving; invalid drafts retain the previous
value and show the invalid line. Empty lists allow no sites. Native parsing
fails closed for malformed JSON/nonarrays and ignores invalid individual
entries. Deduplicate canonical entries; never substitute the default when an
explicit list is empty or invalid. The owning document UA is resolved from its
own container, including container zero; reuse the existing UA Client Hints
product-token classifier and add desktop exclusions without changing its
existing mobile behavior.

Each eligible inner window owns cycle-collected details and N detailed screens,
where N is its validated count snapshot. Repeated calls resolve the same details
object. Its frozen `screens` array holds those same N objects and
`currentScreen === screens[0]`; the first display is the current/primary screen.
`ScreenDetailed` inherits native `Screen`; `ScreenDetails` inherits EventTarget.
Native bindings supply brands, receiver checks, descriptors, and Promise errors.
There are no MAIN-world scripts or JS-installed missing-API polyfills.

The virtual desktop has these invariants:

- `screens.length === N` and `screen.isExtended === (N > 1)`.
- Exactly one screen is primary/current: index zero, with `isInternal === true`;
  additional virtual displays have `isPrimary === false` and `isInternal === false`.
- A one-screen topology uses label "Screen"; multiple screens use stable labels
  "Screen 1", "Screen 2", etc. No physical monitor identifiers are exposed.
- The primary display dimensions, available rectangle, position, orientation,
  color/pixel depth and DPR agree with the owning window's existing persona.
  Additional displays reuse those configured properties and tile horizontally
  to its right; their full/available rectangles move by index × primary width.
  Per-display editing/layout customization is outside this revision.
  Check coordinate arithmetic; overflow uses a coherent deterministic virtual
  fallback for the entire topology, never a physical monitor value.
- Existing screen-value resolution is shared with these getters, using the
  owning window/container rather than a global MaskConfig fallback.
- The same container/domain remains deterministic across reloads; documents
  and containers cannot read each other's values.
- Teardown and retained objects never dereference a destroyed window.

Support `onscreenschange`, `oncurrentscreenchange`, inherited screen `onchange`,
and normal EventTarget listener registration/removal. Physical monitor changes
never alter the virtual topology or emit physical display events. No OS display
enumeration or display-change subscriptions are needed. Getters share existing
screen presentation when saved overrides change; reload affected pages after
UA, master, feature-toggle or allowlist changes to refresh binding exposure.
Saved methods and fresh permission queries immediately recheck all gates.
Changing the allowlist does not grant camera, microphone or physical capture
access. Screen count changes take effect after reload, preserving the frozen
array and detailed-object identities of existing documents. Width, height,
available rectangle, position, orientation, depth and DPR remain configurable
using existing container persona fields, and live geometry changes update all
virtual displays consistently. Do not synthesize topology events for edits.

## Access policy

Only persona data is returned, so this virtual capability does not request OS
screen-enumeration access. An eligible active document has an effective grant
to this virtual capability. Recognize `window-management` in the native
Permissions API: report `granted` for eligible allowed windows and `denied`
elsewhere, including workers. The generic permission-fingerprint mask must not
contradict this state; other permissions remain unchanged.

Honor an explicitly denied `window-management` Permissions Policy: permission
query returns `denied` and invocation rejects with `NotAllowedError`.
Inactive documents reject with `InvalidStateError`. API exposure is decided
when bindings are installed, but saved methods must recheck current eligibility
and document state. No physical display permission is fabricated.
Screen/webcam capture remains the normal Firefox permission-and-chooser flow.

## Delivery and validation

Keep the latest unrelated fixes intact. Native changes are ordered patches,
applied to `firefox-src` and audited against the compiled source. Register new
classes and bindings in Gecko's `moz.build` files and include owned objects in
inner-window cycle collection and cleanup. Add permanent Selenium/geckodriver
probes in `tests/fingerprint/`; do not use Playwright.

Use disposable profiles and local fixtures for the crash regression and API
semantics. Serve local HTTPS fixtures under the allowed hostname using
test-profile-only DNS/certificate configuration, without a production bypass.
Verify first-script availability, descriptors/brands, stable object identity,
frozen array, all screen invariants, listeners, policy denial, lifecycle errors,
origin/UA exclusions, master-off, feature-off, allowlist and count editing/persistence,
counts 1/2/3/8, invalid-count fallback, tiled geometry and stable old-document arrays,
Chrome/Chromium/Edge identity, Firefox-negative controls, reloads and multiple
containers. Test owner-UA resolution across borrowed getters and different
container identities, not only their geometry.

Exercise TestDome's actual codec selection against local synthetic canvas/audio
streams and verify nonempty WebM output. This is separate from physical capture.
Run relevant existing native navigator, worker, UA Client Hints, and permission
regressions. Build and package; repeat targeted probes on the new signed payload,
audit patch reproducibility, and verify the DMG checksum and signature.

Read-only TestDome onboarding with the feature enabled, TestDome allowlisted
and a desktop Chromium identity must remove the unsupported screen-management
message. A Firefox-identity control must keep the new API absent. Independently,
Cloudflare verification keeps the default Firefox identity and must render
without a crashed frame; the screen-management revision does not change that
crash-repair plan. Physical
screen/webcam capture needs the normal user-approved permissions and selection;
do not start a live assessment to establish local API support. Do not claim full
TestDome assessment support until the required capture/recording flow has been
verified through an authorized non-assessment test.

## References

- [Window Management specification](https://w3c.github.io/window-management/)
- `CLAUDE.md`, `patches/navigator-extra-spoofing.patch`, native `WebGPU.webidl`,
  generated `NavigatorBinding.cpp`, and the native `nsScreen` implementation
