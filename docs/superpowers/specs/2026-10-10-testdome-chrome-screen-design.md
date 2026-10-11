# TestDome Chrome identity and virtual screen design

**Date:** 2026-10-10
**Status:** Superseded by [native browser compatibility design](2026-10-10-native-browser-compatibility-design.md)

The subsequent user request asks to use the latest source/DMG and make
TestDome work without Chrome. The linked replacement keeps the Firefox
identity and includes the now-reproduced WebGPU crash cause. This earlier
Chrome-identity proposal is historical, not an implementation requirement.

## Intent and success criteria

The user wants Cloakfox's selected container to identify as Chrome to
TestDome and present exactly one virtual screen. The existing Firefox engine,
native spoofing architecture, and deterministic container identity remain the
implementation foundation.

Success means that TestDome's observed browser/support checks accept the
Chrome identity, its screen initializer obtains a native single-screen result,
and all exposed screen values agree with the container's existing persona.
Live verification stops at onboarding; local fixtures exercise initialization,
events, and rejection behavior. Passing these checks establishes support for
the inspected checks, rather than complete Chromium engine equivalence.

## Evidence

- TestDome's loaded `proctoring-dmqymruf.js` tests
  `"getScreenDetails" in window`, calls `await window.getScreenDetails()`, and
  registers a `screenschange` listener. Its screen consumers read `screens`
  and `currentScreen`. Changing only the User-Agent cannot satisfy this gate.
- Firefox 146 in this checkout has no `getScreenDetails`, `ScreenDetails`,
  `ScreenDetailed`, or `Screen.isExtended` implementation.
- `navigator-spoofing.patch` already derives page and worker `appVersion`
  from the effective navigator UA with the leading `Mozilla/` removed.
  Settings currently spreads independently saved values over the base persona,
  which can leave its displayed `appVersion` stale after editing only the UA.
- `cloakfox-user-agent-data.patch` already supplies native UA Client Hints
  for Chromium UAs. This work reuses that implementation and its regression
  coverage. Native `navigator.vendor` and `productSub` still return Firefox's
  legacy values.
- The installed Chromium-based reference browser on TestDome exposes
  `getScreenDetails`, `vendor === "Google Inc."`, and
  `productSub === "20030107"`; its `appVersion` matches the UA suffix.
  Reading these values did not request screen access or start the assessment.

## Approach

Implement native Gecko bindings and objects. A page-side shim conflicts with
the repository's C++ architecture and would change native object behavior.
Changing the UA alone leaves the confirmed missing-API gate unresolved.

The screen API is narrowly enabled for the HTTPS origin
`https://app.testdome.com`, with Cloakfox enabled and the window's effective
UA identifying as desktop Chrome/Chromium/Edge. Other origins, insecure
contexts, and non-Chromium personas retain the existing absent API. Use the
document principal, never an untrusted URL string or the embedding page's
hostname, to decide eligibility. A same-origin TestDome iframe is eligible;
a cross-origin frame embedded by TestDome is not. Opaque principals are not
eligible.

Chrome identity coherence follows the selected container's effective UA
through the existing override mechanism. It does not change all containers
to Chrome or automatically invent a different identity for every website.
Live validation uses the user's selected Chrome container and reloads the
page after changes.

## Native virtual screen objects

Add `ScreenDetailed` and `ScreenDetails` WebIDL and C++ classes, plus a native
`Window.getScreenDetails()` Promise method and gated `Screen.isExtended`.
`ScreenDetailed` inherits `Screen` and has native getters for `isPrimary`,
`isInternal`, `devicePixelRatio`, and `label`. `ScreenDetails` inherits
`EventTarget`, exposing `screens`, `currentScreen`, `onscreenschange`, and
`oncurrentscreenchange`. The inherited screen event surface supports
`onchange`.

Each eligible inner window owns one cycle-collected `ScreenDetails` and one
`ScreenDetailed`. Repeated calls return the same details object while that
document is alive. `screens` is a native frozen array containing that one
object; `currentScreen === screens[0]`. Native bindings supply descriptor
flags, brand checks, Promise conversion, and illegal-receiver errors. No
MAIN-world scripts, actor-installed polyfills, or instance properties are
added.

The virtual desktop uses these invariants:

- `screens.length === 1` and `screen.isExtended === false`.
- `isPrimary === true`, `isInternal === true`, and `label === "Screen"`.
- Width, height, available rectangle, color/pixel depth, orientation, and
  device pixel ratio use the existing per-container screen presentation.
- Coordinates use one consistent virtual desktop rectangle, shared with
  `window.screen`; no second display position or actual monitor label leaks.
- Values remain deterministic for the same container and domain across
  reloads and do not mix identities between containers or documents.
- Objects resolve values through their owning window, including after
  navigation or detachment; teardown never dereferences a dead window.

The implementation must reuse or factor the existing native screen-value
resolution, rather than separately rereading global MaskConfig defaults.
Physical display enumeration and OS display-change subscriptions are not
needed. Physical monitor changes never change the virtual screen count or
emit topology events. Event listeners can be added and removed normally.
The virtual topology remains fixed during a document lifetime. Attribute
getters share the existing screen presentation so they cannot diverge from
`window.screen` when a saved override changes. Reload after identity or master
changes to update API exposure, as for current UA Client Hints. Live override
edits do not synthesize physical display-change events.

## Access and permission behavior

`getScreenDetails()` returns only persona data and does not ask for access to
physical displays. An eligible document has an effective grant for this
virtual capability. The native Permissions API recognizes
`window-management` and reports `granted` for the eligible document and
`denied` elsewhere. Workers report `denied` because this narrowly scoped
capability belongs to eligible windows. Existing camera, microphone, and
other permission behavior is preserved. The generic permission-fingerprint
mask must not contradict the virtual capability's state.

Respect document lifecycle and the `window-management` Permissions Policy:
an explicitly denied policy yields `denied` and a rejected `NotAllowedError`
Promise. Add this feature to Gecko's policy integration for this capability.
Inactive documents reject with `InvalidStateError`. Screen access returns no
physical information even when an origin is eligible. API availability is
determined when bindings are installed; saved methods must still recheck
eligibility and document state when invoked.

## Chrome identity coherence

Use one effective UA per navigator/container for UA Client Hints and the
legacy browser fields. With Cloakfox enabled and a desktop Chromium UA,
native navigator getters return `vendor === "Google Inc."` and
`productSub === "20030107"`. Firefox personas and master-off behavior keep
their existing values. Reuse a shared native Chromium-UA predicate with
complete product-token parsing; do not introduce inconsistent substring
checks or interpret Chrome on iOS as Chromium.

For a valid Mozilla-style UA, show `appVersion` in Settings as the derived
effective value. Make this field read-only and explain its derivation in the
field's help text. Existing saved `appVersion` preferences need not be deleted;
they do not supersede the native derived value for this UA format. Keep the
existing fallback behavior for other formats.

When the user edits the navigator UA, update the User-Agent header override
to the same value through the existing parent-process override path. Keep the
header field's advanced control, but live validation must flag an independently
edited header that disagrees with navigator UA. Changing UA alone must not
leave the base persona's Firefox header behind. Derive the existing HTTP/2
profile from this effective UA; keep current HTTP/3/TLS limitations documented.
OS/platform consistency uses the existing persona/override choices, with
tests confirming that the selected Chrome identity's platform and hints agree.

## Files and delivery

Deliver native changes as ordered patches in `patches/`, applied to
`firefox-src` and included in native builds. Register new C++/WebIDL files in
their Gecko `moz.build` files and store the owned screen objects in the inner
window with cycle collection and cleanup. Keep Chrome predicate reuse within
the native navigator code rather than duplicating JS browser classification.

Update the relevant override/Settings modules in
`additions/browser/components/cloakfox/`, add Selenium probes under
`tests/fingerprint/`, and update its README and PENDING with actual results.
Only task-specific changes are staged; the checkout contains existing work
that must be preserved.

## Verification

Use Selenium/geckodriver with disposable profiles and local fixtures. Resolve
the allowed hostname to a local HTTPS fixture with certificate handling
confined to the disposable test profile; do not add a production test bypass.

Verify first-script availability, native classes/prototypes/descriptors,
single frozen array, object identity, all screen invariants, event listener
registration/removal, rejected invocation on an ineligible or inactive
document, policy denial, and absence outside the scope. Exercise same-origin
and cross-origin frames, two different containers, reloads, master-off,
Firefox UA, and identity changes followed by reload.

Verify navigator/header/appVersion/Client Hints agreement on local requests,
the Settings UA-edit flow and reload persistence, plus legacy browser getters.
Run the existing UA Client Hints, navigator/worker coherence, and override
regressions. Build and package the native app; repeat the targeted probe on
the packaged binary and audit that the ordered patches reproduce the compiled
source. Read-only TestDome onboarding verification checks removal of the
unsupported-browser message; local fixtures supply the screen initializer
coverage without starting a live assessment.

## Separate Cloudflare crash finding

The supplied CapitalOne screenshot shows the red icon used by Firefox's
`aboutFrameCrashed.css` and `incontent-icons/tab-crashed.svg`, inside the
Cloudflare widget. This supports a crashed embedded frame. The earlier
CodeSignal `frame-ancestors` console error concerns another frame after the
redirect and does not explain the screenshot.

This build disables crash reporting in `mozconfig`; no matching recent
Cloakfox crash dump was found. The crash trigger is unconfirmed. Diagnose it
separately with a reproducible case and process crash evidence before changing
spoofing code. This screen-compatibility feature does not claim to fix the
Cloudflare crash.

## References

- [Window Management specification](https://w3c.github.io/window-management/)
- [Chromium navigator identity implementation](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/frame/navigator_id.cc)
- `CLAUDE.md`, `patches/navigator-spoofing.patch`,
  `patches/cloakfox-user-agent-data.patch`, and the native `nsScreen` code
