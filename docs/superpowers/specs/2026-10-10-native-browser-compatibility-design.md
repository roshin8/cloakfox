# Cloakfox native browser compatibility design

**Date:** 2026-10-10
**Status:** Revised written spec awaiting user review

## Requested outcome

Use the latest Cloakfox source and DMG to repair the crashed Cloudflare widget
and support TestDome in Cloakfox. Keep the default Firefox identity; a Chrome
identity override is not a prerequisite. The previously requested single
virtual screen remains the TestDome presentation. This replaces the earlier
Chrome-identity design; UA/header/Settings refactoring is outside this revision.

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
declare `GPU? gpu` in `WebGPU.webidl`. This adds the generated null check
before DOM wrapping, preserving the intentional no-GPU result. Keep the native
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
Enable these surfaces only for an HTTPS document with the exact principal origin
`https://app.testdome.com` and `cloakfox.enabled=true`. Both Firefox and Chromium
personas are eligible. Other origins, insecure contexts, opaque principals,
workers, and master-off retain the existing absent screen-management surface.
A same-origin TestDome child document is eligible; an unrelated child frame
embedded by TestDome is not. Do not enable by trusting a top-level URL string.

Each eligible inner window owns cycle-collected details and one detailed screen.
Repeated calls resolve the same details object. Its frozen `screens` array holds
exactly that object and `currentScreen === screens[0]`.
`ScreenDetailed` inherits native `Screen`; `ScreenDetails` inherits EventTarget.
Native bindings supply brands, receiver checks, descriptors, and Promise errors.
There are no MAIN-world scripts or JS-installed missing-API polyfills.

The virtual desktop has these invariants:

- `screens.length === 1`, `screen.isExtended === false`, and
  `isPrimary === true` / `isInternal === true`.
- `label === "Screen"`; no physical monitor identifiers are exposed.
- Dimensions, available rectangle, position, orientation, color/pixel depth,
  and device pixel ratio agree with the owning window's existing persona.
- Existing screen-value resolution is shared with these getters, using the
  owning window/container rather than a global MaskConfig fallback.
- The same container/domain remains deterministic across reloads; documents
  and containers cannot read each other's values.
- Teardown and retained objects never dereference a destroyed window.

Support `onscreenschange`, `oncurrentscreenchange`, inherited screen `onchange`,
and normal EventTarget listener registration/removal. Physical monitor changes
never alter the virtual topology or emit physical display events. No OS display
enumeration or display-change subscriptions are needed. Getters share existing
screen presentation when saved overrides change; reload after identity/master
changes to refresh binding exposure. Do not synthesize topology events for edits.

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
origin exclusions, master-off, Firefox identity, reloads, and multiple containers.

Exercise TestDome's actual codec selection against local synthetic canvas/audio
streams and verify nonempty WebM output. This is separate from physical capture.
Run relevant existing native navigator, worker, UA Client Hints, and permission
regressions. Build and package; repeat targeted probes on the new signed payload,
audit patch reproducibility, and verify the DMG checksum and signature.

Read-only live onboarding must remove the unsupported screen-management message
under Firefox identity and render Cloudflare without a crashed frame. Physical
screen/webcam capture needs the normal user-approved permissions and selection;
do not start a live assessment to establish local API support. Do not claim full
TestDome assessment support until the required capture/recording flow has been
verified through an authorized non-assessment test.

## References

- [Window Management specification](https://w3c.github.io/window-management/)
- `CLAUDE.md`, `patches/navigator-extra-spoofing.patch`, native `WebGPU.webidl`,
  generated `NavigatorBinding.cpp`, and the native `nsScreen` implementation
