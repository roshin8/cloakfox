# TestDome Native Screen Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let TestDome's inspected screen-management capability gate work in Cloakfox with its default Firefox identity and the approved single virtual screen.

**Architecture:** Share a window-owned native screen presentation between the existing Screen getters and new cycle-collected ScreenDetailed/ScreenDetails objects. Expose the new bindings only to the approved HTTPS principal with the master enabled, and integrate a virtual window-management permission with real document policy/lifecycle checks. Preserve Firefox's actual camera and display-capture flows.

**Tech Stack:** Gecko 146 C++/WebIDL, cycle collection, FeaturePolicy, native Permissions API, ordered patches, Selenium/geckodriver, local TLS fixtures, WebCodecs/MediaRecorder.

**Spec:** `docs/superpowers/specs/2026-10-10-native-browser-compatibility-design.md`

## Global Constraints

- “Keep the default Firefox identity; a Chrome identity override is not a prerequisite.”
- “Enable these surfaces only for an HTTPS document with the exact principal origin `https://app.testdome.com` and `cloakfox.enabled=true`.”
- “Both Firefox and Chromium personas are eligible.”
- “Other origins, insecure contexts, opaque principals, workers, and master-off retain the existing absent screen-management surface.”
- “There are no MAIN-world scripts or JS-installed missing-API polyfills.”
- “Physical monitor changes never alter the virtual topology or emit physical display events.”
- “Screen/webcam capture remains the normal Firefox permission-and-chooser flow.”
- “Keep the latest unrelated fixes intact.”
- “Add permanent Selenium/geckodriver probes in `tests/fingerprint/`; do not use Playwright.”
- “Do not claim full TestDome assessment support until the required capture/recording flow has been verified through an authorized non-assessment test.”
- Keep the current native checkout/build cache; never run `make dir` or `scripts/patch.py` to apply these incremental patches. Do not edit production DNS/certificate trust, the installed app, or the active profile.

## Review Focus

1. A getter is invoked from another container/realm, especially container zero: resolve its **owner**, not the executing global or a global fallback (Task 1).
2. An explicit modern policy denial is ignored because Gecko 146 only reads Feature-Policy: reject and propagate the denial into children (Task 3).
3. Retained screen objects/methods outlive a frame: preserve safe owned data and reject inactive calls without dereferencing a destroyed window (Tasks 1–2).
4. Scope checks match a parent or a lookalike hostname: exclude opaque/cross-origin/insecure/alternate-port documents while allowing a same-origin child (Task 2).
5. Codec support claims pass but recording stalls: use a headful synthetic fixture and verify nonempty encoded bytes at the actual TestDome settings (Task 4).

---

## File Map and Delivery Order

Task 1 introduces a focused presentation/access helper and fixes owner resolution only for the approved virtual-screen presentation. Task 2 adds native screen objects and exposure. Task 3 adds permission queries and header-policy integration; invocation policy is checked in Task 2 and becomes fully testable when Task 3 registers the policy name. Task 4 validates synthetic recording and the signed payload. Ship the screen feature after all four tasks pass, not after the intermediate Task 2 build.

Outer-repo deliverables:

- `patches/cloakfox-screen-presentation.patch`: shared native owned presentation and origin predicate.
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
- Modify `dom/base/nsScreen.{h,cpp}`, `ScreenOrientation.cpp`, `nsGlobalWindowInner.{h,cpp}`, `moz.build`.
- Create `dom/webidl/ScreenDetailed.webidl`, `ScreenDetails.webidl`; modify `Screen.webidl`, `Window.webidl`, `Permissions.webidl`, `moz.build`.
- Modify `dom/permission/Permissions.cpp`, `PermissionStatus.cpp`, `PermissionUtils.cpp`.
- Modify `dom/security/featurepolicy/FeaturePolicy.{h,cpp}`, `FeaturePolicyUtils.cpp`, and `dom/base/Document.cpp` for the bounded modern header denial.

### Task 1: Establish an owner-based virtual screen presentation

**Files:** Create `screen_management_fixture.py`, `probe_screen_presentation.py`, `cloakfox-screen-presentation.patch`; apply the presentation helper and changes to nsScreen/ScreenOrientation/Window DPR listed above. Modify `patches/order.txt`.

**Interfaces:**
- Consumes: `CloakConfigOverlay_Get(uint32_t userContextId) -> std::string`, `nsPIDOMWindowInner::GetExtantDoc()`, `GetBrowsingContext()->OriginAttributesRef().mUserContextId`, existing `UseCloakfoxLetterboxing(const Document*)`.
- Produces: `CloakfoxScreenAccess::IsEligible(nsPIDOMWindowInner*) -> bool`, `IsEnabled(JSContext*, JSObject*) -> bool`; `CloakfoxScreenPresentation::Read(nsPIDOMWindowInner*) -> Maybe<CloakfoxScreenPresentation>`; `nsScreen::GetVirtualPresentation() const -> const CloakfoxScreenPresentation*`. Python `ScreenManagementFixture(binary: str, headful: bool = False)` context manager provides `driver`, `chrome(script, *args)`, `open(path, host='app.testdome.com', scheme='https', container=0)`, `set_config(container, updates)`, `set_master(enabled)`, and `report_path`.

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

Use the existing `probe_media_permissions.py` chrome-context pattern with `--allow-system-access`. Local handlers serve only fixture resources and fail unknown paths. Assert the fixture receives every allowed-host request; no fixture navigation may reach the real TestDome network. Record `location.origin` and `isSecureContext` before assertions. Start/stop servers and driver in context-manager `try/finally`; preserve reports outside the temporary profile. An additional loopback 8443 TLS listener covers alternate-port exclusion later.

- [ ] **Step 2: Add red presentation tests with explicit pins.** Set container 0 to Firefox/1366x768, available rectangle `{left:0,top:0,width:1300,height:728}`, pixel/color depth 24 and DPR 1; container 2 to Firefox/1920x1080, available `{left:0,top:25,width:1880,height:1030}`, depth 30 and DPR 2. Add a portrait case with explicit orientation type. Disable letterboxing **only in that fixture profile** to make pinned geometry assertions exact; also run a second case with letterboxing enabled to compare existing screen/DPR semantics.

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

Verify exact pinned available dimensions, repeat reads/reloads, two containers, live saved override updates, and scope-off behavior. Use a privileged test-only call to another tab's Screen getter to prove default-container zero does not get reinterpreted as the caller's nonzero container. Retain a removed child's screen/orientation objects, then read them while a second window has different pins; require survival and no substitution of that second window's persona.

```python
assert result['availWidth'] == 1300
assert result['availHeight'] == 728
assert result['dpr'] == 1
```

Run `CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox python3 tests/fingerprint/probe_screen_presentation.py`. Expected red: current GetAvailRect derives full width/height-minus-top instead of the explicit available rectangle, and current realm-relative fallbacks can resolve the wrong owner. Preserve the observed assertion failure; do not weaken pins to match the defect.

- [ ] **Step 3: Implement the shared helper and exact principal predicate.** Use the owning window's document/principal; compare `GetOriginNoSuffix()` exactly, without a top-level URL or prefix match. Require main thread, nonchrome window, a nonopaque content principal, secure context, HTTPS principal URI and `StaticPrefs::cloakfox_enabled()`.

```cpp
namespace mozilla::dom {
struct CloakfoxScreenPresentation {
  CSSIntRect mRect;
  CSSIntRect mAvailRect;
  int32_t mDepth = 24;
  double mDevicePixelRatio = 1.0;
  OrientationType mOrientation = OrientationType::Landscape_primary;
  uint16_t mAngle = 0;
  static Maybe<CloakfoxScreenPresentation> Read(nsPIDOMWindowInner* aWindow);
};
class CloakfoxScreenAccess final {
 public:
  static bool IsEligible(nsPIDOMWindowInner* aWindow);
  static bool IsEnabled(JSContext* aCx, JSObject* aGlobal);
};
}
```

```cpp
nsAutoCString origin;
nsIPrincipal* principal = doc->NodePrincipal();
if (!principal->IsContentPrincipal() ||
    NS_FAILED(principal->GetOriginNoSuffix(origin)) ||
    !origin.EqualsLiteral("https://app.testdome.com")) {
  return false;
}
```

`IsEnabled` obtains `xpc::WindowOrNull(aGlobal)` only on the main thread, then calls IsEligible; active state/policy are invocation checks, not exposure criteria. In Read, obtain `userContextId` from the owner, parse **`CloakConfigOverlay_Get(userContextId)` directly**, including explicit zero. Do not call `MaskConfig::GetInt32(key, ucid)` here: its current implementation ignores the argument; zero also means current context in other MaskConfig entry points. Do not expand this task into a global MaskConfig refactor.

Read only from a fully active owner; an inactive owner returns Nothing so retained objects use their last owned snapshot. Read the same documented persona keys for width/height, available rectangle, depth, `window.devicePixelRatio`, and `screen:orientation:type`. Parse only typed finite numbers; bounds-check int32 dimensions/depth, require positive dimensions/DPR, use deterministic virtual defaults 1920x1080/24-bit/DPR1 if an eligible persona field is absent or invalid. Preserve signed positions, and keep available rectangle coherent inside the virtual rectangle. Use `screen.pixelDepth` when no valid colorDepth exists; normal Screen reports the same depth for both. Default position is zero. Primary orientation angle is 0 and secondary is 180. Reuse existing letterboxing presentation when enabled: top-inner RFP rectangle, native zoom-derived DPR and orientation from that rectangle; no physical screen fallback for eligible virtual data.

- [ ] **Step 4: Route both existing and future detailed getters through that owned helper.** Add a mutable `Maybe<CloakfoxScreenPresentation> mVirtualPresentation` on nsScreen, initialized **before** constructing its ScreenOrientation. GetVirtualPresentation refreshes from its original owner while eligible; when that owner is detached it keeps only the last owned snapshot, never another current inner window's config. Call it at the beginning of GetRect/GetAvailRect/PixelDepth/GetOrientationAngle/GetOrientationType. Eligible virtual paths return its fields; other screens retain their current native/legacy paths.

```cpp
const CloakfoxScreenPresentation* nsScreen::GetVirtualPresentation() const {
  nsPIDOMWindowInner* owner = GetOwnerWindow();
  if (owner && owner->IsFullyActive() &&
      !CloakfoxScreenAccess::IsEligible(owner)) {
    return nullptr;
  }
  if (auto value = CloakfoxScreenPresentation::Read(owner)) {
    mVirtualPresentation = std::move(value);
  }
  return mVirtualPresentation ? mVirtualPresentation.ptr() : nullptr;
}
```

Initialize the cache with Read(aWindow) before constructing mScreenOrientation. An active owner with the master turned off returns to its existing native path; a disconnected/inactive owner retains the last owned snapshot. Convert `mOrientation` to the existing HAL enum for nsScreen's native orientation accessors. In ScreenOrientation's GetType/GetAngle/DeviceType/DeviceAngle, return the screen's owned virtual orientation first for nonsystem callers. Skip `MaybeChanged`/physical orientation dispatch for virtual screens. Make nsScreen's destructor protected for the subclass in Task 2. In `nsGlobalWindowInner::GetDevicePixelRatio`, use Read(this)'s DPR for eligible non-system calls; Read must calculate letterboxing DPR without recursively calling this method. This makes window and detailed DPR share the same owner resolution.

Register the helper header in EXPORTS.mozilla.dom and its cpp in dom/base/moz.build. Generate a patch from saved pre-edit native files, append its order entry, and dry-run/apply it without resetting the checkout. When editing source directly to develop the patch, verify a reverse dry run instead of applying it a second time.

- [ ] **Step 5: Build and verify the independently testable presentation fix.** Run `./mach build` in firefox-src, then the presentation probe on `obj-aarch64-apple-darwin/dist/bin/cloakfox`. Require exact owner pins, live updates, letterboxing coherence, safe retained objects, repeat loads, and unchanged master-off/non-TestDome Screen behavior. Add malformed/wrong-type/negative-size/DPR-NaN inputs and require deterministic coherent virtual fallbacks with no physical substitution. Preserve signed available positions in a valid virtual rectangle case.

- [ ] **Step 6: Commit the focused deliverable.**

```sh
git add patches/cloakfox-screen-presentation.patch patches/order.txt tests/fingerprint/screen_management_fixture.py tests/fingerprint/probe_screen_presentation.py
git commit -m "fix: resolve virtual screen presentation from its owning window"
```

### Task 2: Add native screen objects, bindings, and safe window ownership

**Files:** Create `probe_screen_management.py`, `cloakfox-testdome-screen-management.patch`, ScreenDetailed/ScreenDetails native/WebIDL files. Modify nsScreen, nsGlobalWindowInner, Screen/Window WebIDL and both moz.build files listed in the map.

**Interfaces:**
- Consumes: Task 1's `CloakfoxScreenAccess` and presentation helper and `ScreenManagementFixture`.
- Produces: `ScreenDetailed final : nsScreen`, `ScreenDetails final : DOMEventTargetHelper`, `nsGlobalWindowInner::GetScreenDetails(ErrorResult&) -> already_AddRefed<Promise>`, `nsScreen::IsExtended() const -> bool`.
- ScreenDetails: constructor `(nsPIDOMWindowInner*)`; `GetScreens(nsTArray<RefPtr<ScreenDetailed>>&) const -> void`; `CurrentScreen() const -> ScreenDetailed*`; `WrapObject(JSContext*, JS::Handle<JSObject*>) -> JSObject*`; inherited event handlers.
- ScreenDetailed: constructor `(nsPIDOMWindowInner*)`; `IsPrimary()/IsInternal() const -> bool`; `GetLabel(nsAString&) const -> void`; `DevicePixelRatio() const -> double`; overridden WrapObject.

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
    equal: ['width','height','left','top','availWidth','availHeight','availLeft','availTop','colorDepth','pixelDepth']
      .every(k => s[k] === screen[k]),
    orientation: s.orientation.type === screen.orientation.type && s.orientation.angle === screen.orientation.angle
  };
})();
```

Run the probe on the Task 1 build. Expected: getScreenDetails/ScreenDetails/ScreenDetailed/isExtended are absent and the API test fails. Verify Firefox UA is pinned so a brand override cannot accidentally satisfy the test.

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

- [ ] **Step 3: Implement one native detailed screen and cycle collection.** ScreenDetailed's inherited getters use Task 1's owned presentation. IsPrimary/IsInternal return true; GetLabel assigns `u"Screen"_ns`; DevicePixelRatio uses GetVirtualPresentation and its retained owned fallback. nsScreen::IsExtended returns false. ScreenDetails stores `RefPtr<ScreenDetailed> mScreen`, creates it for its own inner window, and returns that one object:

```cpp
void ScreenDetails::GetScreens(nsTArray<RefPtr<ScreenDetailed>>& aResult) const {
  aResult.AppendElement(mScreen);
}
ScreenDetailed* ScreenDetails::CurrentScreen() const { return mScreen; }

NS_IMPL_CYCLE_COLLECTION_INHERITED(ScreenDetails, DOMEventTargetHelper, mScreen)
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

The Promise rejection helpers above are generated by Promise.h's DOMEXCEPTION macro and DOMExceptionNames.h. Do not call its protected legacy MaybeRejectWithDOMException method. Retained saved methods must recheck eligibility, policy and active state on each invocation. Register new cpp/header/WebIDL files in the existing sorted moz.build lists. Record the exact new file hunk counts in the patch and avoid malformed/truncated new-file hunks.

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

Repeat for currentscreenchange and detailed-screen change, and exercise onscreenschange/oncurrentscreenchange/onchange. Notify `screen-information-changed` from chrome context in this disposable profile, then verify zero **trusted** topology/orientation events and unchanged one-screen topology. Update saved geometry pins and verify shared getters change without topology events.

Test Firefox and Chromium identities with master on; default-container and nonzero-container reloads; same-origin child; unrelated cross-origin child embedded by the eligible parent; opaque sandboxed srcdoc; insecure HTTP; sibling/subdomain/lookalike host; HTTPS port 8443; dedicated/shared/service workers; master off after reload. Excluded Window surfaces and classes must be absent; workers must have neither method nor screen classes. A same-origin inheriting blank document may be eligible by principal/secure context, not by its `about:blank` URL.

Save a method on an eligible window, turn the master off without reload, and require NotAllowedError on invocation. Remove an eligible iframe retaining its method/object, then require an InvalidStateError Promise from the saved method and safe owned screen reads; never silently serve the new active document's persona. Record a same-origin navigation/BFCache-back case: each new inner has its own details identity; restored active inner can resume its original identity safely.

- [ ] **Step 6: Build and run the green native contract suite.** Run `./mach build`, presentation and screen-management probes on dist/bin. Policy-header and permission-query assertions are tagged as Task 3 cases until that patch exists; don't mark final API acceptance complete yet. Commit only the new patch, order and regression code:

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

- [ ] **Step 4: Exercise policy parsing and inheritance failures.** Add extra spacing, a multi-directive dictionary, an absent directive, a valid nonempty list, malformed header and lookalike directive `x-window-management`. Only the valid exact empty-list directive adds denial. Verify denied top-level and nested same-origin children, remote cross-origin child remaining ineligible, iframe denial after changing allow, and master-off query denied with the new API absent after reload. Query from dedicated/shared/service workers returns denied, not its parent's state. Keep `permissions:spoof=true` and prove it doesn't convert the virtual grant/denial to prompt.

- [ ] **Step 5: Build and run complete screen/permission regressions.**

```sh
# First run ./mach build inside firefox-src.
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

- [ ] **Step 6: Inspect read-only TestDome onboarding in the new payload.** Under Firefox identity/master on, load the user-supplied start-test URL and verify the missing-screen-management unsupported message is gone and first-script API exists. Do not click start-test, begin an assessment, alter challenge decisions or approve real device capture. Inspect the Cloudflare link as specified in its independent plan if included. If a new unsupported gate appears, report and diagnose the exact remaining gate instead of saying full compatibility is achieved.

- [ ] **Step 7: Document verified behavior and commit the deliverable.** README explains origin/master scope, native frozen sequence, reload requirements, local probes and standard capture chooser. Verification document records every actual report and signed artifact path/checksum, plus these separate conclusions: native screen API verified; synthetic recording verified; live onboarding observed; physical screen/webcam capture and full assessment support remain unverified unless separately exercised in an authorized non-assessment session.

```sh
git add tests/fingerprint/probe_testdome_recording.py tests/fingerprint/fixtures/testdome_codec_profiles.json tests/fingerprint/README.md docs/superpowers/verification/2026-10-10-browser-compatibility.md
git commit -m "test: verify native TestDome compatibility and signed payload"
```

## Self-review

Spec coverage: exact origin/master and owner/deterministic presentation are Tasks 1–2; native classes/frozen identity/events/teardown and scope exclusion are Task 2; virtual grant, workers, masks and modern/legacy policy denial are Task 3; codec fallback, relevant regressions, reproducible ordered patches, signed DMG and bounded onboarding are Task 4. Each Review Focus case has an owning regression. Interfaces use one owned window and one screen; no global config fallback, new OS display access, UA refactor or page polyfill is planned. Tests distinguish local/native capability from physical capture and full assessment delivery.
