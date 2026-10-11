# TestDome Native Screen Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide configurable native virtual-screen compatibility for allowlisted HTTPS sites, including TestDome, when Cloakfox uses a desktop Chrome/Chromium/Edge identity.

**Architecture:** Share a window-owned native screen presentation between the existing Screen getters and new cycle-collected ScreenDetailed/ScreenDetails objects. Expose the new bindings only when the master, separate feature toggle, owning document's desktop Chromium identity and editable exact-origin allowlist all permit it. Integrate a virtual window-management permission with real document policy/lifecycle checks. Preserve Firefox's actual camera and display-capture flows.

**Tech Stack:** Gecko 146 C++/WebIDL, cycle collection, FeaturePolicy, native Permissions API, ordered patches, Selenium/geckodriver, local TLS fixtures, WebCodecs/MediaRecorder.

**Spec:** `docs/superpowers/specs/2026-10-10-native-browser-compatibility-design.md`

## Global Constraints

- Keep the default browser identity Firefox; this optional API requires a desktop Chrome/Chromium/Edge identity in its owning document.
- Require `cloakfox.enabled=true`, `cloakfox.compat.screen_management=true` and an exact HTTPS principal origin in `cloakfox.compat.screen_management.origins`.
- Default the feature toggle to false and the editable origins JSON array to `["https://app.testdome.com"]`. Empty lists enable no sites; invalid configuration fails closed.
- Exclude Firefox/Safari/mobile identities, unlisted origins, insecure contexts, opaque principals, workers, feature-off and master-off.
- Make virtual screen count configurable from 1–8, default 1, through `cloakfox.compat.screen_management.screen_count`. Wrong-type/out-of-range values fall back to 1.
- Keep the toggle, count dropdown and editable allowlist adjacent in one Settings group.
- Snapshot count per inner window and apply count changes after reload. Primary geometry uses persona fields; additional virtual screens tile horizontally with the same configured properties. No physical monitor enumeration or per-display editor is added.
- “There are no MAIN-world scripts or JS-installed missing-API polyfills.”
- “Physical monitor changes never alter the virtual topology or emit physical display events.”
- “Screen/webcam capture remains the normal Firefox permission-and-chooser flow.”
- “Keep the latest unrelated fixes intact.”
- “Add permanent Selenium/geckodriver probes in `tests/fingerprint/`; do not use Playwright.”
- “Do not claim full TestDome assessment support until the required capture/recording flow has been verified through an authorized non-assessment test.”
- Keep the current native checkout/build cache; never run `make dir` or `scripts/patch.py` to apply these incremental patches. Do not edit production DNS/certificate trust, the installed app, or the active profile.

## Review Focus

1. A getter is invoked from another container/realm, especially container zero: resolve its **owner** for both UA eligibility and geometry, not the executing global or a global fallback (Task 1).
2. An explicit modern policy denial is ignored because Gecko 146 only reads Feature-Policy: reject and propagate the denial into children (Task 3).
3. Retained screen objects/methods outlive a frame: preserve safe owned data and reject inactive calls without dereferencing a destroyed window (Tasks 1–2).
4. Scope/config checks match a parent, caller UA or lookalike hostname, or a count edit invalidates frozen arrays: snapshot count per inner window and test 1/2/3/8 plus invalid values; require the owner's desktop Chromium UA and an exact listed origin; validate editable lists, empty/malformed values, explicit ports and live removal (Tasks 1–2).
5. Codec support claims pass but recording stalls: use a headful synthetic fixture and verify nonempty encoded bytes at the actual TestDome settings (Task 4).

---

## File Map and Delivery Order

Task 1 delivers the toggle/allowlist controls, desktop-UA gate and focused presentation/access helper, and fixes owner resolution only for the eligible virtual-screen presentation. Task 2 adds native screen objects and exposure. Task 3 adds permission queries and header-policy integration; invocation policy is checked in Task 2 and becomes fully testable when Task 3 registers the policy name. Task 4 validates synthetic recording and the signed payload. Ship the screen feature after all four tasks pass, not after the intermediate Task 2 build.

Outer-repo deliverables:

- `patches/cloakfox-screen-presentation.patch`: shared native owned presentation, reusable desktop-UA classifier, toggle and exact allowlist predicate.
- `settings/cloakfox.cfg`: feature-off, initial allowlist and screen-count defaults.
- `additions/browser/components/cloakfox/content/settings.html`, `settings.js`: adjacent feature checkbox, screen-count dropdown and editable origins list, validation and reload guidance.
- `tests/fingerprint/probe_screen_management_settings.py`: actual Settings UI editing, persistence, reset, validation and scope controls.
- `patches/cloakfox-testdome-screen-management.patch`: native objects, WebIDL, Window ownership/exposure.
- `patches/cloakfox-window-management-permission.patch`: permission enum/query and modern denial integration.
- `patches/order.txt`: append those three in that order after all current patches. If the independent WebGPU repair is present, retain its placement after `navigator-extra-spoofing.patch`.
- `tests/fingerprint/screen_management_fixture.py`: disposable TLS/profile fixture, local hostname routing, reports, container tabs.
- `tests/fingerprint/probe_screen_presentation.py`: owner/geometry/orientation regression.
- `tests/fingerprint/probe_screen_management.py`: bindings, lifecycle, events, scope and permission/policy matrix.
- `tests/fingerprint/probe_testdome_recording.py`: local capability selection and synthetic recording.
- `tests/fingerprint/fixtures/testdome_codec_profiles.json`: observed public codec settings with source URL/retrieval date, no assessment/candidate data.
- `tests/fingerprint/README.md`: commands, scope, reload behavior and limits.
- `docs/superpowers/verification/2026-10-10-browser-compatibility.md`: measured build/package/live evidence.

Applied native files (the patches, not the ignored checkout, are committed):

- Create `dom/base/CloakfoxScreenPresentation.{h,cpp}`, `ScreenDetailed.{h,cpp}`, `ScreenDetails.{h,cpp}`.
- Modify `dom/base/nsScreen.{h,cpp}`, `ScreenOrientation.cpp`, `nsGlobalWindowInner.{h,cpp}`, `NavigatorUAData.{h,cpp}`, `moz.build`.
- Create `dom/webidl/ScreenDetailed.webidl`, `ScreenDetails.webidl`; modify `Screen.webidl`, `Window.webidl`, `Permissions.webidl`, `moz.build`.
- Modify `dom/permission/Permissions.cpp`, `PermissionStatus.cpp`, `PermissionUtils.cpp`.
- Modify `dom/security/featurepolicy/FeaturePolicy.{h,cpp}`, `FeaturePolicyUtils.cpp`, and `dom/base/Document.cpp` for the bounded modern header denial.

### Task 1: Establish an owner-based virtual screen presentation

**Files:** Create `screen_management_fixture.py`, `probe_screen_presentation.py`, `probe_screen_management_settings.py`, `cloakfox-screen-presentation.patch`; apply the presentation/access helper, reusable UA classifier and changes to nsScreen/ScreenOrientation/Window DPR listed above. Modify `patches/order.txt`, `settings/cloakfox.cfg` and the existing Settings HTML/JS.

**Interfaces:**
- Consumes: `CloakConfigOverlay_Get(uint32_t userContextId) -> std::string`, `nsPIDOMWindowInner::GetExtantDoc()`, `GetBrowsingContext()->OriginAttributesRef().mUserContextId`, existing `UseCloakfoxLetterboxing(const Document*)`.
- Produces: `CloakfoxScreenAccess::IsEligible(nsPIDOMWindowInner*) -> bool`, `IsEnabled(JSContext*, JSObject*) -> bool`, `ReadUserAgent(nsPIDOMWindowInner*) -> Maybe<nsString>`, `IsOriginAllowed(const nsACString&) -> bool`; `NavigatorUAData::IsDesktopChromiumIdentity(const nsAString&) -> bool`; `CloakfoxScreenPresentation::Read(nsPIDOMWindowInner*, uint32_t screenIndex = 0) -> Maybe<CloakfoxScreenPresentation>`; `nsGlobalWindowInner::GetCloakfoxVirtualScreenCount() const -> uint32_t` returns its constructor-time validated snapshot; `nsScreen::GetVirtualPresentation() const -> const CloakfoxScreenPresentation*`. Python `ScreenManagementFixture(binary: str, headful: bool = False)` context manager provides `driver`, `chrome(script, *args)`, `open(path, host='app.testdome.com', scheme='https', container=0)`, `set_config(container, updates)`, `set_master(enabled)`, `set_feature(enabled)`, `set_origins(origins)`, `set_screen_count(count)` (save then reload to apply), and `report_path`. Tests explicitly enable the feature and pin a desktop Chromium UA; a separate unseeded-profile control checks the shipped disabled default.

- [ ] **Step 1: Add the local TLS fixture.** Generate a one-day self-signed certificate with SANs for `app.testdome.com`, `other.testdome.invalid`, `app.testdome.com.evil.invalid`, and `sub.app.testdome.com`. Bind only loopback ports 443 and 80 so the production exact-origin predicate is exercised. Do not stop a process occupying either port; fail with the port/socket error. Route only these names to loopback via `network.dns.localDomains` in a disposable Firefox profile and use `options.accept_insecure_certs = True` only in that WebDriver profile. No `/etc/hosts` edits, system trust installs or production switches.

```python
server = ThreadingHTTPServer(('127.0.0.1', 443), Handler)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain(cert_path, key_path)
server.socket = tls.wrap_socket(server.socket, server_side=True)
options.binary_location = binary
options.accept_insecure_certs = True
options.set_preference('network.dns.localDomains',
    'app.testdome.com,other.testdome.invalid,app.testdome.com.evil.invalid,sub.app.testdome.com')
options.set_preference('network.trr.mode', 5)
```

Use the existing `probe_media_permissions.py` chrome-context pattern with `--allow-system-access`. Local handlers serve only fixture resources and fail unknown paths. Assert the fixture receives every allowed-host request; no fixture navigation may reach the real TestDome network. Record `location.origin` and `isSecureContext` before assertions. Start/stop servers and driver in context-manager `try/finally`; preserve reports outside the temporary profile. An additional loopback 8443 TLS listener covers default alternate-port exclusion and explicit-port allowlisting later. Add `other.testdome.invalid` to the allowlist only in positive editable-list tests; it remains excluded by default. Neither test hostname represents a production site selection.

- [ ] **Step 2: Add red presentation tests with explicit pins.** With the feature enabled and TestDome listed, set container 0 to desktop Chrome/1366x768, available rectangle `{left:0,top:0,width:1300,height:728}`, pixel/color depth 24 and DPR 1; container 2 to desktop Edge/1920x1080, available `{left:0,top:25,width:1880,height:1030}`, depth 30 and DPR 2. Add a portrait case with explicit orientation type. Disable letterboxing **only in that fixture profile** to make pinned geometry assertions exact; also run a second case with letterboxing enabled to compare existing screen/DPR semantics.

```javascript
window.presentation = () => ({
  width: screen.width, height: screen.height,
  left: screen.left, top: screen.top,
  availWidth: screen.availWidth, availHeight: screen.availHeight,
  availLeft: screen.availLeft, availTop: screen.availTop,
  colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,
  dpr: devicePixelRatio, type: screen.orientation.type,
  angle: screen.orientation.angle
});
```

Verify exact pinned available dimensions, repeat reads/reloads, two containers, live saved override updates, and master/feature-off, Firefox-UA and removed-origin behavior. Use a privileged test-only call to another tab's Screen getter to prove default-container zero does not get reinterpreted as the caller's nonzero container. Retain a removed child's screen/orientation objects, then read them while a second window has different pins; require survival and no substitution of that second window's persona.

```python
assert result['availWidth'] == 1300
assert result['availHeight'] == 728
assert result['dpr'] == 1
```

Run `CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox python3 tests/fingerprint/probe_screen_presentation.py`. Expected red: current GetAvailRect derives full width/height-minus-top instead of the explicit available rectangle, and current realm-relative fallbacks can resolve the wrong owner. Preserve the observed assertion failure; do not weaken pins to match the defect.

- [ ] **Step 3: Implement the settings controls and owner-based access helper.** Require main thread, nonchrome window, a nonopaque content principal, secure context, HTTPS principal URI, the master, the feature toggle, a listed exact principal origin and the owner's desktop Chromium UA. Keep these checks centralized in IsEligible so exposure, invocation, geometry and permission queries agree.

Add shipped defaults:

```javascript
defaultPref("cloakfox.compat.screen_management", false);
defaultPref("cloakfox.compat.screen_management.screen_count", 1);
defaultPref("cloakfox.compat.screen_management.origins",
  '["https://app.testdome.com"]');
```

Use main-thread `Preferences::GetBool`/`GetCString` for the eligibility preferences and `Preferences::GetInt` for the screen count; verify content-process propagation and live changes in the probe. Add a checkbox using the existing `data-pref` binding and a multiline exact-origin editor with explicit **Save origins** and **Reset origins** buttons. Label the feature **Virtual screen-management API** and explain that it requires a desktop Chromium identity, reports the selected virtual screen count and still uses normal capture permissions. Place the toggle, **Virtual screen count** dropdown and origins editor together in one card; the count and list are directly beside/below the toggle, adapting to narrow windows. Show reload guidance beside all controls. The dropdown offers 1–8, defaults to 1 and saves an integer pref using `setIntPref`; give it ID `cfx-screen-count`. Geometry continues to use the existing Display persona controls. Explain that extra displays reuse that geometry in a horizontal layout. Reset restores only the default origins list; it does not enable the feature or reset personas. Use stable element IDs `cfx-screen-management`, `cfx-screen-origins`, `cfx-screen-origins-save`, `cfx-screen-origins-reset` and an aria-live error/status element `cfx-screen-origins-status`. On load, render the saved JSON array as one origin per line; visibly report malformed stored values instead of displaying the default as if it were saved.

The privileged Settings save handler validates the complete draft before writing the JSON preference. Preserve the previous saved value on any invalid line, show that line's error, deduplicate canonical origins, and allow an empty editor to save `[]`:

```javascript
function parseScreenManagementOrigins(text) {
  const origins = [];
  for (const [index, line] of text.split(/\r?\n/).entries()) {
    const value = line.trim();
    if (!value) continue;
    let url;
    try { url = new URL(value); }
    catch { throw new Error(`Line ${index + 1}: enter a complete HTTPS origin.`); }
    if (url.protocol !== "https:" || url.username || url.password ||
        url.pathname !== "/" || url.search || url.hash ||
        !url.hostname || url.hostname.includes("*")) {
      throw new Error(`Line ${index + 1}: use an exact HTTPS origin without a path or wildcard.`);
    }
    if (!origins.includes(url.origin)) origins.push(url.origin);
  }
  return origins;
}
const editor = document.getElementById("cfx-screen-origins");
const status = document.getElementById("cfx-screen-origins-status");
document.getElementById("cfx-screen-origins-save").addEventListener("click", () => {
  try {
    const origins = parseScreenManagementOrigins(editor.value);
    Services.prefs.setStringPref("cloakfox.compat.screen_management.origins",
      JSON.stringify(origins));
    editor.value = origins.join("\n");
    status.textContent = "Saved. Reload affected pages to update API availability.";
  } catch (error) {
    status.textContent = error.message;
  }
});
```

`IsOriginAllowed` parses the same JSON array natively, canonicalizes candidates through `NS_NewURI` and principal origin serialization, and compares exact origins. Reject credentials, non-HTTPS, non-origin paths/query/fragment/wildcards; ignore invalid entries and fail closed on malformed JSON/nonarrays. Empty/invalid lists do not fall back to TestDome. Nondefault ports qualify only when explicitly listed. Read the document principal, never the parent URL or a prefix/substring match.

```cpp
namespace mozilla::dom {
struct CloakfoxScreenPresentation {
  CSSIntRect mRect;
  CSSIntRect mAvailRect;
  int32_t mDepth = 24;
  double mDevicePixelRatio = 1.0;
  OrientationType mOrientation = OrientationType::Landscape_primary;
  uint16_t mAngle = 0;
  uint32_t mScreenCount = 1;
  uint32_t mScreenIndex = 0;
  static Maybe<CloakfoxScreenPresentation> Read(
      nsPIDOMWindowInner* aWindow, uint32_t aScreenIndex = 0);
};
class CloakfoxScreenAccess final {
 public:
  static bool IsEligible(nsPIDOMWindowInner* aWindow);
  static bool IsEnabled(JSContext* aCx, JSObject* aGlobal);
  static Maybe<nsString> ReadUserAgent(nsPIDOMWindowInner* aWindow);
  static bool IsOriginAllowed(const nsACString& aOrigin);
};
}
```

```cpp
nsAutoCString origin;
nsIPrincipal* principal = doc->NodePrincipal();
if (!principal->IsContentPrincipal() ||
    NS_FAILED(principal->GetOriginNoSuffix(origin)) ||
    !IsOriginAllowed(origin)) {
  return false;
}
```

Resolve UA from the owning window's explicit container: first `NavigatorManager::GetUserAgent(ucid, ua)`, then the string `navigator.userAgent` in `CloakConfigOverlay_Get(ucid)`, including zero. If both are absent, use the existing owner-aware static native `Navigator::GetUserAgent(window, doc, Nothing(), ua)` fallback; errors fail eligibility. Do not use the executing global or a `MaskConfig::GetString` context fallback for a borrowed getter. Verify the resolved value agrees with that owner's page-facing navigator in normal and borrowed-receiver tests.

Expose `NavigatorUAData::IsDesktopChromiumIdentity(const nsAString&)` as a C++ helper reusing its existing complete-product-token `IsChromiumUA` parser. Require a valid Chrome/Chromium product (Edge includes Chrome) and exclude Android, Mobile, iPhone and iPad tokens. Keep mixed Firefox+Chrome tokens and malformed products excluded. Do not change the existing UA Client Hints classifier/mobile behavior or introduce a page-visible method.

```cpp
if (!StaticPrefs::cloakfox_enabled() ||
    !Preferences::GetBool("cloakfox.compat.screen_management", false)) {
  return false;
}
auto ua = ReadUserAgent(aWindow);
if (!ua || !NavigatorUAData::IsDesktopChromiumIdentity(*ua)) return false;
```

`IsEnabled` obtains `xpc::WindowOrNull(aGlobal)` only on the main thread, then calls IsEligible; active state/policy are invocation checks, not exposure criteria. In Read, obtain `userContextId` from the owner, parse **`CloakConfigOverlay_Get(userContextId)` directly**, including explicit zero. Do not call `MaskConfig::GetInt32(key, ucid)` here: its current implementation ignores the argument; zero also means current context in other MaskConfig entry points. Do not expand this task into a global MaskConfig refactor.

Read only from a fully active owner; an inactive owner returns Nothing so retained objects use their last owned snapshot. Read the same documented persona keys for width/height, available rectangle, depth, `window.devicePixelRatio`, and `screen:orientation:type`. Parse only typed finite numbers; bounds-check int32 dimensions/depth, require positive dimensions/DPR, use deterministic virtual defaults 1920x1080/24-bit/DPR1 if an eligible persona field is absent or invalid. Preserve signed positions, and keep available rectangle coherent inside the virtual rectangle. Use `screen.pixelDepth` when no valid colorDepth exists; normal Screen reports the same depth for both. Default position is zero. Primary orientation angle is 0 and secondary is 180. Reuse existing letterboxing presentation when enabled: top-inner RFP rectangle, native zoom-derived DPR and orientation from that rectangle; no physical screen fallback for eligible virtual data.

Snapshot a validated count in each `nsGlobalWindowInner` constructor: read the integer pref, accept 1–8, otherwise store 1 in `mCloakfoxVirtualScreenCount`. Expose only the C++ getter `GetCloakfoxVirtualScreenCount() const`. Count changes do not alter an existing inner window's value; a newly loaded inner window reads the saved preference. This keeps `screen.isExtended`, detailed screens and their frozen array coherent even if they are first accessed at different times. The count does not depend on a physical display or another window.

Read defaults to index zero for ordinary Screen/DPR callers. For detailed index i, require i < the owner's cached count; set mScreenCount/mScreenIndex, reuse primary size/depth/orientation/DPR and shift both full and available rectangles by i × primary width along x. Validate the entire topology's maximum coordinate using checked int64 arithmetic before narrowing to int32; on overflow use a coherent 1920×1080, 24-bit, DPR1 virtual base at (0,0) for every index. Never silently reduce the selected count or fall back to physical screens. Live primary-persona updates recompute each display's geometry, preserving indices and object identities.

- [ ] **Step 4: Route both existing and future detailed getters through that owned helper.** Add a mutable `Maybe<CloakfoxScreenPresentation> mVirtualPresentation` and immutable `uint32_t mVirtualScreenIndex` on nsScreen, initialized **before** constructing its ScreenOrientation. Extend its native constructor with an optional index argument defaulting to zero; ScreenDetailed passes its own index. GetVirtualPresentation refreshes from its original owner while eligible; when that owner is detached it keeps only the last owned snapshot, never another current inner window's config. Call it at the beginning of GetRect/GetAvailRect/PixelDepth/GetOrientationAngle/GetOrientationType. Eligible virtual paths return its fields; other screens retain their current native/legacy paths.

```cpp
const CloakfoxScreenPresentation* nsScreen::GetVirtualPresentation() const {
  nsPIDOMWindowInner* owner = GetOwnerWindow();
  if (owner && owner->IsFullyActive() &&
      !CloakfoxScreenAccess::IsEligible(owner)) {
    return nullptr;
  }
  if (auto value = CloakfoxScreenPresentation::Read(owner, mVirtualScreenIndex)) {
    mVirtualPresentation = std::move(value);
  }
  return mVirtualPresentation ? mVirtualPresentation.ptr() : nullptr;
}
```

Initialize the cache with Read(aWindow, mVirtualScreenIndex) before constructing mScreenOrientation. An active owner with the master turned off returns to its existing native path; a disconnected/inactive owner retains the last owned snapshot. Convert `mOrientation` to the existing HAL enum for nsScreen's native orientation accessors. In ScreenOrientation's GetType/GetAngle/DeviceType/DeviceAngle, return the screen's owned virtual orientation first for nonsystem callers. Skip `MaybeChanged`/physical orientation dispatch for virtual screens. Make nsScreen's destructor protected for the subclass in Task 2. In `nsGlobalWindowInner::GetDevicePixelRatio`, use Read(this)'s DPR for eligible non-system calls; Read must calculate letterboxing DPR without recursively calling this method. This makes window and detailed DPR share the same owner resolution.

Register the helper header in EXPORTS.mozilla.dom and its cpp in dom/base/moz.build. Generate a patch from saved pre-edit native files, append its order entry, and dry-run/apply it without resetting the checkout. When editing source directly to develop the patch, verify a reverse dry run instead of applying it a second time.

- [ ] **Step 5: Build and verify the independently testable presentation fix.** Run `./mach build` in firefox-src, then the presentation probe on `obj-aarch64-apple-darwin/dist/bin/cloakfox`. Require exact owner pins, live updates, letterboxing coherence, safe retained objects, repeat loads, and unchanged master-off/feature-off/Firefox-UA/unlisted-origin Screen behavior. Run `probe_screen_management_settings.py` against the same build: operate the real checkbox/count dropdown/editor, check their adjacent placement, save count 2 and two valid origins, reject invalid drafts without changing the pref, clear/reset the list, reload and restart to verify count/list persistence. Verify the count pref default 1 and integer values 1/2/3/8 survive reloads. Add cases for 0/-1/9 and wrong pref types: the Settings selection must show fallback 1. Full native count/frozen-array assertions run in Task 2, once detailed-screen bindings exist; changing the pref must then leave an existing inner window's cached count unchanged. Verify native eligibility responds to edits in existing content processes. Cover canonical host case/default-port normalization, explicit 8443, duplicate entries, wildcard/path/credential/HTTP rejection, malformed stored JSON, nonarrays and empty lists. Pair a Firefox owner in container 0 with Chrome in container 2 and test borrowed calls in both directions: neither caller can supply eligibility to the other owner. Add malformed/wrong-type/negative-size/DPR-NaN inputs and require deterministic coherent virtual fallbacks with no physical substitution. Preserve signed available positions in a valid virtual rectangle case.

- [ ] **Step 6: Commit the focused deliverable.**

```sh
git add patches/cloakfox-screen-presentation.patch patches/order.txt settings/cloakfox.cfg additions/browser/components/cloakfox/content/settings.html additions/browser/components/cloakfox/content/settings.js tests/fingerprint/screen_management_fixture.py tests/fingerprint/probe_screen_presentation.py tests/fingerprint/probe_screen_management_settings.py
git commit -m "fix: resolve virtual screen presentation from its owning window"
```

### Task 2: Add native screen objects, bindings, and safe window ownership

**Files:** Create `probe_screen_management.py`, `cloakfox-testdome-screen-management.patch`, ScreenDetailed/ScreenDetails native/WebIDL files. Modify nsScreen, nsGlobalWindowInner, Screen/Window WebIDL and both moz.build files listed in the map.

**Interfaces:**
- Consumes: Task 1's `CloakfoxScreenAccess` and presentation helper and `ScreenManagementFixture`.
- Produces: `ScreenDetailed final : nsScreen`, `ScreenDetails final : DOMEventTargetHelper`, `nsGlobalWindowInner::GetScreenDetails(ErrorResult&) -> already_AddRefed<Promise>`, `nsScreen::IsExtended() const -> bool`.
- ScreenDetails: constructor `(nsPIDOMWindowInner*)`; `GetScreens(nsTArray<RefPtr<ScreenDetailed>>&) const -> void`; `CurrentScreen() const -> ScreenDetailed*`; `WrapObject(JSContext*, JS::Handle<JSObject*>) -> JSObject*`; inherited event handlers.
- ScreenDetailed: constructor `(nsPIDOMWindowInner*, uint32_t screenIndex)`; `IsPrimary()/IsInternal() const -> bool`; `GetLabel(nsAString&) const -> void`; `DevicePixelRatio() const -> double`; overridden WrapObject.

- [ ] **Step 1: Add the failing first-script native API test.** Run the collector as an inline script at the start of the TLS document, not after WebDriver injects anything.

```javascript
window.firstScriptSupport = {
  method: typeof window.getScreenDetails,
  details: typeof ScreenDetails, detailed: typeof ScreenDetailed,
  extended: 'isExtended' in screen,
  ua: navigator.userAgent
};
window.result = (async () => {
  const a = await window.getScreenDetails();
  const b = await window.getScreenDetails();
  const s = a.currentScreen;
  return {
    same: a === b, frozen: Object.isFrozen(a.screens),
    sameArray: a.screens === a.screens, count: a.screens.length,
    current: s === a.screens[0],
    brands: [Object.prototype.toString.call(a), Object.prototype.toString.call(s)],
    inheritance: s instanceof Screen && s instanceof ScreenDetailed && a instanceof EventTarget,
    extended: screen.isExtended, primary: s.isPrimary, internal: s.isInternal,
    label: s.label, dpr: s.devicePixelRatio,
    displays: a.screens.map(display => ({
      primary: display.isPrimary, internal: display.isInternal, label: display.label,
      width: display.width, height: display.height,
      left: display.left, top: display.top,
      availWidth: display.availWidth, availHeight: display.availHeight,
      availLeft: display.availLeft, availTop: display.availTop,
      depth: display.colorDepth, pixelDepth: display.pixelDepth,
      dpr: display.devicePixelRatio,
      orientation: display.orientation.type, angle: display.orientation.angle
    })),
    equal: ['width','height','left','top','availWidth','availHeight','availLeft','availTop','colorDepth','pixelDepth']
      .every(k => s[k] === screen[k]),
    orientation: s.orientation.type === screen.orientation.type && s.orientation.angle === screen.orientation.angle
  };
})();
```

Run the probe on the Task 1 build. Expected: getScreenDetails/ScreenDetails/ScreenDetailed/isExtended are absent and the API test fails. Pin a desktop Chrome UA, explicitly enable the feature and list the fixture origin. Also run a Firefox-UA negative control requiring method/classes/isExtended to remain absent. Do not infer success from changing UA alone.

- [ ] **Step 2: Add native WebIDL using Gecko's frozen-sequence convention.** General FrozenArray is not implemented in this Gecko version; use the established `[Cached, Constant, Frozen] sequence` binding to obtain the same JS frozen-array contract. Do not add hand-built JS arrays or binding-generator changes.

```webidl
[Exposed=Window, SecureContext, Func="mozilla::dom::CloakfoxScreenAccess::IsEnabled"]
interface ScreenDetailed : Screen {
  readonly attribute boolean isPrimary;
  readonly attribute boolean isInternal;
  readonly attribute DOMString label;
  readonly attribute double devicePixelRatio;
};

[Exposed=Window, SecureContext, Func="mozilla::dom::CloakfoxScreenAccess::IsEnabled"]
interface ScreenDetails : EventTarget {
  [Cached, Constant, Frozen] readonly attribute sequence<ScreenDetailed> screens;
  readonly attribute ScreenDetailed currentScreen;
  attribute EventHandler onscreenschange;
  attribute EventHandler oncurrentscreenchange;
};

partial interface Window {
  [SecureContext, Func="mozilla::dom::CloakfoxScreenAccess::IsEnabled", Throws]
  Promise<ScreenDetails> getScreenDetails();
};

partial interface Screen {
  [SecureContext, Func="mozilla::dom::CloakfoxScreenAccess::IsEnabled"]
  readonly attribute boolean isExtended;
};
```

Include `mozilla/dom/CloakfoxScreenPresentation.h` in nsScreen.h, nsGlobalWindowInner.h, ScreenDetails.h and ScreenDetailed.h so the native binding headers make the predicate visible. Existing Screen's Bindings.conf mapping to nsScreen remains unchanged; the new interfaces use Gecko's default mozilla::dom names/header paths. Native functions, brands and receiver checks come from bindings. No WebIDL constructor is added.

- [ ] **Step 3: Implement N native detailed screens and cycle collection.** ScreenDetailed's inherited getters use Task 1's owned/indexed presentation. IsPrimary/IsInternal are true only for index zero; GetLabel returns "Screen" for N=1, otherwise "Screen " plus the one-based index. DevicePixelRatio uses GetVirtualPresentation and its retained owned fallback. nsScreen::IsExtended checks the owner's cached presentation count > 1. ScreenDetails stores `nsTArray<RefPtr<ScreenDetailed>> mScreens` and constructs N objects for its own inner window, with N from GetCloakfoxVirtualScreenCount():

```cpp
ScreenDetails::ScreenDetails(nsPIDOMWindowInner* aWindow)
    : DOMEventTargetHelper(aWindow) {
  const uint32_t count = aWindow->GetCloakfoxVirtualScreenCount();
  for (uint32_t index = 0; index < count; ++index) {
    mScreens.AppendElement(new ScreenDetailed(aWindow, index));
  }
}
void ScreenDetails::GetScreens(nsTArray<RefPtr<ScreenDetailed>>& aResult) const {
  aResult.AppendElements(mScreens);
}
ScreenDetailed* ScreenDetails::CurrentScreen() const { return mScreens[0]; }

NS_IMPL_CYCLE_COLLECTION_INHERITED(ScreenDetails, DOMEventTargetHelper, mScreens)
NS_IMPL_ADDREF_INHERITED(ScreenDetails, DOMEventTargetHelper)
NS_IMPL_RELEASE_INHERITED(ScreenDetails, DOMEventTargetHelper)
NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(ScreenDetails)
NS_INTERFACE_MAP_END_INHERITING(DOMEventTargetHelper)
```

Declare matching `NS_DECL_ISUPPORTS_INHERITED` and cycle-collection macros in both classes. ScreenDetailed inherits nsScreen's cycle traversal and adds no second global/window pointer. Its interface map and AddRef/Release inherit nsScreen. Use `ScreenDetails_Binding::Wrap` and `ScreenDetailed_Binding::Wrap`. Implement `IMPL_EVENT_HANDLER(screenschange)` and `IMPL_EVENT_HANDLER(currentscreenchange)`; inherited nsScreen supplies onchange and EventTarget. No OS enumeration, new display observers, topology mutation or physical event dispatch.

- [ ] **Step 4: Implement invocation and lifetime checks on the owner window.** Add `RefPtr<ScreenDetails> mScreenDetails` to nsGlobalWindowInner; traverse/unlink it alongside other owned DOM objects and clear it in FreeInnerObjects. Do not copy the existing mScreen omission in cycle traversal. No global/static details cache.

```cpp
already_AddRefed<Promise> nsGlobalWindowInner::GetScreenDetails(ErrorResult& aRv) {
  RefPtr<Promise> promise = Promise::Create(this, aRv);
  if (aRv.Failed()) return nullptr;
  if (!IsFullyActive() || !GetExtantDoc()) {
    promise->MaybeRejectWithInvalidStateError("The document is not fully active.");
    return promise.forget();
  }
  if (!CloakfoxScreenAccess::IsEligible(this) ||
      !FeaturePolicyUtils::IsFeatureAllowed(GetExtantDoc(), u"window-management"_ns)) {
    promise->MaybeRejectWithNotAllowedError("Window management is not allowed.");
    return promise.forget();
  }
  if (!mScreenDetails) mScreenDetails = new ScreenDetails(this);
  promise->MaybeResolve(mScreenDetails);
  return promise.forget();
}
```

The Promise rejection helpers above are generated by Promise.h's DOMEXCEPTION macro and DOMExceptionNames.h. Do not call its protected legacy MaybeRejectWithDOMException method. Retained saved methods must recheck eligibility, policy and active state on each invocation. Screen-count edits do not revoke access; they take effect only in new inner windows, while all four access gates still recheck immediately. Register new cpp/header/WebIDL files in the existing sorted moz.build lists. Record the exact new file hunk counts in the patch and avoid malformed/truncated new-file hunks.

- [ ] **Step 5: Extend the native contract, scope, events and lifecycle matrix.** Assert the collector's fields above, `s.devicePixelRatio === window.devicePixelRatio`, frozen array mutation failure, readonly native descriptor flags, no own `getScreenDetails` property, native function text, illegal-receiver TypeError, correct instanceof/brands and no public constructors. Listener add/remove and event-handler assignments are exercised with page-generated untrusted events, preserving native EventTarget behavior:

```javascript
let calls = 0;
const listener = () => ++calls;
details.addEventListener('screenschange', listener);
details.dispatchEvent(new Event('screenschange'));
details.removeEventListener('screenschange', listener);
details.dispatchEvent(new Event('screenschange'));
if (calls !== 1) throw new Error('Native listener removal failed');
```

Repeat for currentscreenchange and detailed-screen change, and exercise onscreenschange/oncurrentscreenchange/onchange. Notify `screen-information-changed` from chrome context in this disposable profile, then verify zero **trusted** topology/orientation events and unchanged configured N-screen topology. Repeat the API collector for counts 1/2/3/8, require `screens.length === N`, exactly one primary/internal display, `currentScreen === screens[0]`, `screen.isExtended === (N > 1)`, stable labels and horizontal full/available rectangles. Assert all displays share the primary depth/DPR/orientation and its size; cover negative primary positions and coordinate-overflow fallback. Change count on an already loaded document: its array identity, length and isExtended must remain unchanged with no trusted topology event. After reload, the new inner window must expose the new count coherently. Retained old objects must remain safe. Update saved geometry pins and verify shared getters change without topology events.

Test Chrome, Chromium and Edge identities with master/feature on and Firefox, Safari, mixed/malformed product and mobile-UA negative controls; default-container and nonzero-container reloads; same-origin child; unrelated cross-origin child embedded by the eligible parent; opaque sandboxed srcdoc; insecure HTTP; sibling/subdomain/lookalike host; HTTPS port 8443 absent until explicitly allowlisted; default and edited lists; dedicated/shared/service workers; master or feature off after reload. Excluded Window surfaces and classes must be absent; workers must have neither method nor screen classes. A same-origin inheriting blank document may be eligible by principal/secure context, not by its `about:blank` URL.

Save a method on an eligible window, then independently disable the master, disable the feature, remove its origin and switch its owner UA to Firefox without reload; each change must make invocation reject with NotAllowedError. Reload after each binding-exposure change and require the surface absent. Re-enable/re-add/select Chromium and reload to restore it. Allowlisted sites cannot enable the feature or change the list from web content. Remove an eligible iframe retaining its method/object, then require an InvalidStateError Promise from the saved method and safe owned screen reads; never silently serve the new active document's persona. Record a same-origin navigation/BFCache-back case: each new inner has its own details identity; restored active inner can resume its original identity safely.

- [ ] **Step 6: Build and run the green native contract suite.** Run `./mach build`, Settings, presentation and screen-management probes on dist/bin. The Settings probe now verifies both saved preferences and first-script API exposure after reload/restart; in Task 1 it checks eligibility through the presentation helper only. Policy-header and permission-query assertions are tagged as Task 3 cases until that patch exists; don't mark final API acceptance complete yet. Commit only the new patch, order and regression code:

```sh
git add patches/cloakfox-testdome-screen-management.patch patches/order.txt tests/fingerprint/probe_screen_management.py
git commit -m "feat: add scoped native TestDome screen management"
```

### Task 3: Integrate virtual permission state and explicit document-policy denial

**Files:** Create `cloakfox-window-management-permission.patch`; modify permissions, feature-policy and Document.cpp files from the map; extend `probe_screen_management.py` and fixture policy routes.

**Interfaces:**
- Consumes: `CloakfoxScreenAccess::IsEligible(nsPIDOMWindowInner*)`, Task 2 GetScreenDetails policy check, `FeaturePolicyUtils::IsFeatureAllowed(Document*, const nsAString&)`.
- Produces: `PermissionName::Window_management`; native query resolves `PermissionStatus` granted only for an eligible active allowed Window, denied elsewhere including workers; `FeaturePolicy::DenyFeatureByHeader(const nsAString&) -> void`; `FeaturePolicyUtils::ApplyWindowManagementDenial(Document*, const nsACString&) -> void`.

- [ ] **Step 1: Write and run the red permission/policy assertions.** Add routes with no policy, modern `Permissions-Policy: window-management=()`, legacy `Feature-Policy: window-management 'none'`, same-origin iframe `allow="window-management 'none'"`, a parent denied header with an otherwise allowing child, and a parent with unrelated policy directives. Query and invocation share the expected outcome:

```javascript
const state = (await navigator.permissions.query({name: 'window-management'})).state;
let result;
try { await getScreenDetails(); result = 'resolved'; }
catch (e) { result = e.name; }
// For explicit denial: state === 'denied' and result === 'NotAllowedError'.
// For eligible allowed: state === 'granted' and result === 'resolved'.
```

Expected red on Task 2 build: query rejects for unsupported PermissionName; modern denial isn't parsed and must fail the denial expectation. Workers must query denied even when their ancestor is eligible. Also assert media permission names keep the existing actual-grant/revocation behavior and notification masking remains prompt.

- [ ] **Step 2: Add the permission enum/type and virtual initialization.** Append `"window-management"` to Permissions.webidl and the matching `"window-management"_ns` entry to PermissionUtils.cpp's ordered kPermissionTypes array, preserving its static_assert. Add Window_management to Permissions.cpp's ordinary PermissionStatus creation cases. In PermissionStatus::Init(), short-circuit **before CreateSink** for this permission, keeping workers denied and avoiding permission-manager/OS prompts or the generic spoof mask:

```cpp
if (mName == PermissionName::Window_management) {
  mState = PermissionState::Denied;
  if (NS_IsMainThread()) {
    nsGlobalWindowInner* window = GetOwnerWindow();
    if (window && window->IsFullyActive() &&
        CloakfoxScreenAccess::IsEligible(window) &&
        FeaturePolicyUtils::IsFeatureAllowed(window->GetExtantDoc(), u"window-management"_ns)) {
      mState = PermissionState::Granted;
    }
  }
  return SimplePromise::CreateAndResolve(NS_OK, __func__);
}
```

A queried status describes the effective virtual grant at query time; new queries/calls recheck live state. Existing Permissions::Query already rejects inactive Windows. Do not route a worker through its ancestor grant in PermissionStatusSink. Do not modify actual camera/microphone grants, display capture, permission prompts, or chooser selection. Add only the includes needed for native origin/policy checks.

- [ ] **Step 3: Register the policy feature and bounded modern denial parsing.** Add `{"window-management", FeaturePolicyUtils::FeaturePolicyValue::eSelf}` to sSupportedFeatures, so existing iframe allow/legacy header inheritance is effective. Add the public DenyFeatureByHeader method to FeaturePolicy as a thin call to existing SetInheritedDeniedFeature; this preserves denial in ToFeaturePolicyInfo/remote-frame inheritance without replacing unrelated declared directives.

```cpp
void FeaturePolicy::DenyFeatureByHeader(const nsAString& aName) {
  if (!HasInheritedDeniedFeature(aName)) SetInheritedDeniedFeature(aName);
}

void FeaturePolicyUtils::ApplyWindowManagementDenial(
    Document* aDocument, const nsACString& aHeader) {
  nsCOMPtr<nsISFVService> service = mozilla::net::GetSFVService();
  nsCOMPtr<nsISFVDictionary> dictionary;
  if (!service || NS_FAILED(service->ParseDictionary(aHeader, getter_AddRefs(dictionary)))) return;
  nsCOMPtr<nsISFVItemOrInnerList> entry;
  if (NS_FAILED(dictionary->Get("window-management"_ns, getter_AddRefs(entry)))) return;
  nsCOMPtr<nsISFVInnerList> list = do_QueryInterface(entry);
  if (!list) return;
  nsTArray<RefPtr<nsISFVItem>> items;
  if (NS_SUCCEEDED(list->GetItems(items)) && items.IsEmpty()) {
    aDocument->FeaturePolicy()->DenyFeatureByHeader(u"window-management"_ns);
  }
}
```

Use Gecko's exported `mozilla/net/SFVService.h` and generated `nsIStructuredFieldValues.h`; its GetItems signature accepts `nsTArray<RefPtr<nsISFVItem>>&`. Document::InitFeaturePolicy reads `Permissions-Policy` from its own response channel and calls this helper after inherited/legacy policy initialization. Process the bounded modern denial even if the pref for the **legacy** header is off. No regex/substr matching and no broad modern-policy implementation: this revision supports only explicit empty-list window-management denial plus existing iframe/legacy policy semantics. Modern allowlists don't expand the principal scope, override ancestor denial, or grant physical permission.

- [ ] **Step 4: Exercise policy parsing and inheritance failures.** Add extra spacing, a multi-directive dictionary, an absent directive, a valid nonempty list, malformed header and lookalike directive `x-window-management`. Only the valid exact empty-list directive adds denial. Verify denied top-level and nested same-origin children, remote cross-origin child remaining ineligible, iframe denial after changing allow, and master-off/feature-off/Firefox-UA/unlisted-origin query denied with the new API absent after reload. Fresh queries must observe live gate changes without a restart. Query from dedicated/shared/service workers returns denied, not its parent's state. Keep `permissions:spoof=true` and prove it doesn't convert the virtual grant/denial to prompt.

- [ ] **Step 5: Build and run complete screen/permission regressions.**

```sh
# First run ./mach build inside firefox-src.
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_screen_management_settings.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_screen_presentation.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_screen_management.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_media_permissions.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_user_agent_data.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_worker_container.py
```

Expected: all cases pass; this is now the complete scoped API acceptance gate. Audit new patch application/reversal against current native files, then commit:

```sh
git add patches/cloakfox-window-management-permission.patch patches/order.txt tests/fingerprint/probe_screen_management.py tests/fingerprint/screen_management_fixture.py
git commit -m "feat: enforce native virtual window-management access policy"
```

### Task 4: Verify the actual codec fallback, package, and read-only onboarding

**Files:** Create `probe_testdome_recording.py`, codec profile fixture; modify README; create/update the verification document. Produce one new named signed DMG, optionally combining final validation with the independent Cloudflare plan.

**Interfaces:**
- Consumes: Task 1 `ScreenManagementFixture(..., headful=True)`, complete API/permission tests, observed TestDome profile settings.
- Produces: `CLOAKFOX_BIN=<binary> REPORT_DIR=<directory> python3 tests/fingerprint/probe_testdome_recording.py` report/exit status; signed mounted-payload reports and artifact checksum; bounded live onboarding evidence.

- [ ] **Step 1: Preserve actual public codec settings as a fixture.** Use the observed AppSettings profile order: hardware-preference H.264/VP9/AV1/VP8, then no-preference H.264/VP8. Screen is 1920x1080x15 with bpp .05; webcam 640x360x15 with bpp .08 for H.264/VP8/VP9 and .03 for AV1, audio 64000. Preserve the exact codec arrays from `/tmp/cloakfox-compat-20261010/probe_codecs.py` and the recorded public config; include its source/retrieval date. Prefer a fresh read-only public config verification if those temporary files disappeared. Do not copy live assessment bundles/candidate data into the repository.

- [ ] **Step 2: Add a failing-test guard against empty output/timeouts and implement the synthetic probe.** Use the observed profile selection checks, requiring both native VideoEncoder support and MediaRecorder MIME support. Select the first supported profile in actual order; do not hard-code hardware H.264 success. Run headful, with autoplay permissions relaxed only in the disposable fixture profile. Create canvas video and oscillator audio without microphone/screen access:

```javascript
const encoderConfig = {codec: 'vp8', width: 1920, height: 1080,
  framerate: 15, bitrate: 1920 * 1080 * 15 * .05, hardwareAcceleration: 'no-preference'};
const supported = await VideoEncoder.isConfigSupported(encoderConfig);
if (!supported.supported || !MediaRecorder.isTypeSupported('video/webm;codecs=vp8'))
  throw new Error('Observed VP8 fallback is not supported');
const canvas = document.createElement('canvas');
canvas.width = 1920; canvas.height = 1080;
const stream = canvas.captureStream(15);
const recorder = new MediaRecorder(stream, {mimeType:'video/webm;codecs=vp8',
  videoBitsPerSecond: encoderConfig.bitrate});
```

The full profile loop mirrors the observed selection, with this fallback as an explicit assertion. Reuse the demonstrated `/tmp/cloakfox-compat-20261010/probe_recording.py` recording sequence, changing the fixed binary path to CLOAKFOX_BIN. Paint changing frames for at least 550 ms; collect dataavailable blobs, stop the recorder, and check nonzero bytes plus `[26,69,223,163]` EBML header for VP8/WebM. Run webcam 640x360x15 with an AudioContext oscillator feeding createMediaStreamDestination and MIME `video/webm;codecs=vp8,opus`. Stop every track/oscillator, close AudioContext, clear timers and remove canvases even on failure.

```python
assert screen_result['bytes'] > 0
assert screen_result['ebml'] == [26, 69, 223, 163]
assert webcam_result['bytes'] > 0
assert webcam_result['ebml'] == [26, 69, 223, 163]
```

Add a 45-second bounded timeout and diagnostic progress state; inject an empty-blob test case and verify the Python guard fails before using the real recorder. The real pre-change browser already records successfully headful, so do not invent a red codec defect. This test guards a capability regression and records the supported fallback; synthetic encoding doesn't establish physical capture or remote delivery.

- [ ] **Step 3: Run all relevant checks once on the final dev build.** Run Tasks 1–3 probes, recording, native navigator/worker/UAData/media-permission regressions, and the WebGPU probe if its independent fix is included. Document failures and fix only those caused by these changes. No broad unrelated suite reruns after the relevant checks pass.

- [ ] **Step 4: Audit patches and produce the signed artifact.** Run `bash scripts/test-patches.sh` in its separate extraction, inspect failures and compare the newly patched native files to compiled input using a retained scratch extraction. Do not reset firefox-src. Run `./mach package`; stage only the resulting app and Applications symlink in a unique temp directory, verify/sign with local ad-hoc codesign if needed, and create a new filename `cloakfox-146.0.1-beta.25-browser-compat-20261010.dmg` (timestamp suffix if present). Use the Cloudflare plan Task 2 signing/mount commands if both plans execute, with just one final DMG.

- [ ] **Step 5: Verify the mounted payload, not a stale app.** Mount read-only to a unique temp path, run the presentation/API/permission/recording and optional WebGPU probes on that app executable with disposable profiles, verify codesign, BuildID, XUL/executable hashes and final DMG SHA-256. Detach only the mount created for this verification. Preserve all previous DMGs and leave the installed app/user profile unchanged.

- [ ] **Step 6: Inspect read-only TestDome onboarding in the new payload.** With a desktop Chromium identity, master/feature on and the TestDome exact origin allowlisted, load the user-supplied start-test URL and verify the missing-screen-management unsupported message is gone and first-script API exists. Do not click start-test, begin an assessment, alter challenge decisions or approve real device capture. Run a separate Firefox-UA control that confirms the new API is absent, without claiming TestDome support for that identity. Inspect the Cloudflare link under its independent Firefox-identity plan if included. If a new unsupported gate appears, report and diagnose the exact remaining gate instead of saying full compatibility is achieved.

- [ ] **Step 7: Document verified behavior and commit the deliverable.** README explains the four eligibility gates, feature-off default, Settings checkbox and editable exact-origin list, configurable count (1–8, default 1), adjacent controls, count-after-reload semantics and persona-based tiled geometry, native frozen sequence, reload requirements, local probes and standard capture chooser. Verification document records every actual report and signed artifact path/checksum, plus these separate conclusions: native screen API verified; synthetic recording verified; live onboarding observed; physical screen/webcam capture and full assessment support remain unverified unless separately exercised in an authorized non-assessment session.

```sh
git add tests/fingerprint/probe_testdome_recording.py tests/fingerprint/fixtures/testdome_codec_profiles.json tests/fingerprint/README.md docs/superpowers/verification/2026-10-10-browser-compatibility.md
git commit -m "test: verify native TestDome compatibility and signed payload"
```

## Self-review

Spec coverage: owner-based desktop Chromium UA, master/feature gates, configurable exact-origin allowlist, Settings validation/count/list persistence, immutable per-document topology and owner/deterministic presentation are Tasks 1–2; native classes/frozen identity/events/teardown and scope exclusion are Task 2; virtual grant, workers, masks and modern/legacy policy denial are Task 3; codec fallback, relevant regressions, reproducible ordered patches, signed DMG and bounded onboarding are Task 4. Each Review Focus case has an owning regression. Interfaces use one owned window and a validated array of 1–8 virtual screens; no global config fallback, new OS display access, UA refactor or page polyfill is planned. Tests distinguish local/native capability from physical capture and full assessment delivery.
