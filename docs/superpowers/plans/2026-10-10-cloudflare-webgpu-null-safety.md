# Cloudflare WebGPU Null Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the native null-WebGPU getter from crashing Cloudflare's frame in the latest Cloakfox build.

**Architecture:** Change the WebIDL return contract to nullable while keeping the existing native getter and privacy actor. A permanent local Selenium reproducer checks both the value and content-process survival. This repair can be built and verified independently of the screen-management plan.

**Tech Stack:** Firefox 146.0.1 C++, WebIDL, ordered patches, Python/Selenium, geckodriver, macOS packaging.

**Spec:** `docs/superpowers/specs/2026-10-10-native-browser-compatibility-design.md`

## Global Constraints

- “Keep the latest unrelated fixes intact.”
- “Keep the native getter, `[SameObject]`, secure-context restriction, and existing actor behavior.”
- “Master-off and WebGPU-enabled cases still return their native GPU object.”
- “Add permanent Selenium/geckodriver probes in `tests/fingerprint/`; do not use Playwright.”
- “The live verification target is a functioning widget with no process crash; challenge acceptance remains the service's decision.”
- Work in the current checkout. Do not run `make dir`, `scripts/patch.py`, reset the native checkout, overwrite an existing DMG, or alter the installed app/user profile.

## Review Focus

1. WebDriver returns null after a child crash: a separate same-document sentinel and native log must still fail the regression (Task 1).
2. A blank or srcdoc realm bypasses the existing actor: the native disabled getter must return null safely (Task 1).
3. A frame navigates while a native getter is retained: current and saved receivers must not crash (Task 1).
4. Workers share the modified WebIDL mixin: their native enabled GPU object must remain valid (Task 1).
5. Packaging accidentally includes stale XUL: rerun the regression on the mounted signed payload, not only the dev binary (Task 2).

---

## File Map

- `patches/cloakfox-webgpu-null-safety.patch`: one WebIDL contract change.
- `patches/order.txt`: register the patch immediately after `navigator-extra-spoofing.patch`.
- `firefox-src/dom/webidl/WebGPU.webidl`: applied build input; ignored native checkout, not the outer-repo deliverable.
- `tests/fingerprint/probe_webgpu_null_safety.py`: local frame/worker regression, process-liveness assertion, JSON report.
- `tests/fingerprint/README.md`: commands and limits of the verification.
- `docs/superpowers/verification/2026-10-10-browser-compatibility.md`: append build, payload and live-widget evidence; shared only if both plans execute.

### Task 1: Preserve the crash reproducer and repair the binding

**Files:** Create the patch and probe above; modify `patches/order.txt`, `tests/fingerprint/README.md`, and the applied `firefox-src/dom/webidl/WebGPU.webidl:87`.

**Interfaces:**
- Consumes: `Navigator::Gpu() -> mozilla::webgpu::Instance*`; null is the intentional disabled return. `WorkerNavigator::Gpu()` continues returning a native instance.
- Produces: nullable generated `Navigator_Binding::get_gpu` and `WorkerNavigator_Binding::get_gpu`; probe invocation `CLOAKFOX_BIN=<binary> REPORT_DIR=<directory> python3 tests/fingerprint/probe_webgpu_null_safety.py`, exit zero only if every matrix case and liveness check passes.

- [ ] **Step 1: Add the local probe and explicit survival assertion.** Use `ThreadingHTTPServer` on `127.0.0.1:0`, a disposable profile per master case, and `Service(service_args=['--allow-system-access'], log_output=<report>/gecko-<case>.log)`. Read the binary from `CLOAKFOX_BIN`, never a fixed installed app path. Copy the already reproduced minimal page from `/tmp/cloakfox-compat-20261010/repro_gpu.py` into permanent test code, then extend the page to normal, blank, srcdoc, and navigated frames. The blank-frame core is:

```javascript
const frame = document.createElement('iframe');
frame.src = 'about:blank';
document.body.append(frame);
window.crashProbeToken = crypto.randomUUID();
const n = frame.contentWindow.navigator;
const getter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(n), 'gpu').get;
window.runCrashProbe = () => {
const a = getter.call(n), b = getter.call(n);
window.crashProbeResult = {isNull: a === null, type: typeof a, same: a === b};
};
```

```python
token = driver.execute_script('return window.crashProbeToken')
driver.execute_script('window.runCrashProbe()')
result = driver.execute_script('return window.crashProbeResult')
assert isinstance(result, dict), 'Getter did not finish in the original document'
assert driver.execute_script('return window.crashProbeToken') == token
driver.execute_script('document.body.dataset.probeAlive = "yes"')
assert driver.execute_script('return document.body.dataset.probeAlive') == 'yes'
```

The setup script captures the realm/getter without invoking it; Python captures the token **before** invoking runCrashProbe. On exceptions, preserve the report and fail; quit the disposable driver in `finally`. After quit, fail on `exited on signal 11`, `EXC_BAD_ACCESS`, or a crashed-frame marker in the corresponding native log. Never interpret a null WebDriver response as the expected native null result.

- [ ] **Step 2: Run the red test on the current payload.**

```sh
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox REPORT_DIR=/tmp/cloakfox-webgpu-before python3 tests/fingerprint/probe_webgpu_null_safety.py
```

Expected: the master-off control passes; master-on blank-frame case fails the completion/liveness assertion or records signal 11. This launches only disposable profiles.

- [ ] **Step 3: Apply the exact nullable change as an ordered patch.**

```diff
 interface mixin NavigatorGPU {
-  [SameObject, Func="mozilla::webgpu::Instance::PrefEnabled", SecureContext] readonly attribute GPU gpu;
+  [SameObject, Func="mozilla::webgpu::Instance::PrefEnabled", SecureContext] readonly attribute GPU? gpu;
 };
```

Generate the patch from before/after copies with `a/dom/webidl/WebGPU.webidl` and `b/dom/webidl/WebGPU.webidl` headers. Dry-run and apply only this new patch to the current source:

```sh
patch --dry-run -d firefox-src -p1 -i ../patches/cloakfox-webgpu-null-safety.patch
patch -d firefox-src -p1 -i ../patches/cloakfox-webgpu-null-safety.patch
```

Do not change `Navigator::Gpu()`, `Instance::PrefEnabled`, worker implementation, persona defaults or actors.

- [ ] **Step 4: Complete the value and realm matrix.** In master-on normal/srcdoc/navigated pages the actor may return undefined; record that presentation without replacing it. In an unpatched blank frame assert native null when disabled. For the enabled-native-object control, disable only `navigator:webgpu:disabled` in the disposable overlay and exercise a blank realm. Master-off and enabled-native blank getters must return an object with `a === b`. Test descriptor receiver rejection on `{}` and `[native code]` on the raw native getter. Create a dedicated worker on the local secure loopback origin and check `typeof navigator.gpu === 'object'` and stable object identity; the mixin nullability must not disable worker GPUs.

```javascript
// Worker fixture; post the result without requesting any adapter/device.
const a = navigator.gpu;
postMessage({type: typeof a, same: a === navigator.gpu, nonnull: a !== null});
```

For navigation, retain `{getter, navigator}` in the parent, navigate the child to another local document, then call the saved getter on its original receiver. Assert survival independently; a torn-down realm may reject, but must never crash or access a new window's data. Obtain a fresh getter from the new realm and assert its expected actor/native result.

- [ ] **Step 5: Build the WebIDL change and run green verification.** From `firefox-src` run `./mach build` (a WebIDL change needs binding regeneration, not only `mach build binaries`). Use `obj-aarch64-apple-darwin/dist/bin/cloakfox` for the dev probe. Verify the generated `obj-aarch64-apple-darwin/dom/bindings/NavigatorBinding.cpp` nullable branch handles null before calling `GetOrCreateDOMReflector`. Run the probe and existing worker/navigator regressions:

```sh
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" REPORT_DIR=/tmp/cloakfox-webgpu-after python3 tests/fingerprint/probe_webgpu_null_safety.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_navigator_coherence.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox" python3 tests/fingerprint/probe_workers.py
```

Expected: no process deaths, enabled native identity intact, and existing tests pass. Add the permanent probe command and evidence limits to the README.

- [ ] **Step 6: Commit only this deliverable.**

```sh
git add patches/cloakfox-webgpu-null-safety.patch patches/order.txt tests/fingerprint/probe_webgpu_null_safety.py tests/fingerprint/README.md
git commit -m "fix: make the disabled native WebGPU binding null-safe"
```

### Task 2: Verify a fresh signed payload and the supplied live widget

**Files:** Create/update `docs/superpowers/verification/2026-10-10-browser-compatibility.md`; produce a new named DMG, preserving all older artifacts.

**Interfaces:**
- Consumes: Task 1's green probe and compiled native binary; current macOS build/package configuration.
- Produces: mounted-payload probe report, SHA-256/signature evidence, and read-only Cloudflare outcome with a precise statement of what was verified.

- [ ] **Step 1: Check freshness and preserve the build baseline.** Record outer-repo HEAD, native patch diff, `upstream.sh`, application BuildID, and SHA-256 of the compiled executable/XUL. If the screen plan executes immediately afterward, combine this task with its final packaging task and run **both** probe sets on that payload. The Cloudflare patch remains independently buildable/testable; do not do two full packages unnecessarily.

- [ ] **Step 2: Produce a newly named signed DMG.** Run `./mach package` inside `firefox-src`. Inspect the resulting app signature before creating the final DMG; if the package output is unsigned, sign a separate staging copy, never `/Applications/Cloakfox.app`:

```sh
codesign --force --deep --sign - /tmp/cloakfox-compat-package/Cloakfox.app
codesign --verify --deep --strict /tmp/cloakfox-compat-package/Cloakfox.app
hdiutil create -volname Cloakfox -srcfolder /tmp/cloakfox-compat-package -ov -format UDZO cloakfox-146.0.1-beta.25-browser-compat-20261010.dmg
shasum -a 256 cloakfox-146.0.1-beta.25-browser-compat-20261010.dmg
```

Create a fresh staging directory containing only the package's app and an Applications symlink. If that exact output filename already exists, choose a timestamp suffix; do not use `-ov` on a preexisting final artifact. This is ad-hoc local signing, not a Developer ID/notarization claim.

- [ ] **Step 3: Mount this DMG read-only at a unique `/tmp` path and rerun Task 1's probe on its actual executable.** Compare its executable and XUL SHA-256 with the staging app, verify `codesign --verify --deep --strict`, and preserve BuildID/report before detaching only our mount. A stale packaged library is a test failure even if the dev build passed.

- [ ] **Step 4: Inspect the user-supplied CapitalOne link in the new app using a disposable profile with Firefox identity and the master on.** Observe the Cloudflare frame and capture a screenshot/native log. Do not click a CAPTCHA, sign in, or start an assessment. A normal verifying/challenge widget with no crashed frame is the repair criterion; acceptance is recorded separately. If it still crashes, obtain the new stack and continue diagnosis rather than declaring the patch sufficient.

- [ ] **Step 5: Audit patch reproducibility and document the measured result.** Run `bash scripts/test-patches.sh` against its separate extraction, inspect all results, and compare the repaired WebIDL there with the applied build input before its cleanup (or retain a separate scratch extraction for that comparison). Record any unrelated preexisting audit failures without rewriting unrelated patches. Commit the verification document only after evidence exists:

```sh
git add docs/superpowers/verification/2026-10-10-browser-compatibility.md
git commit -m "docs: record signed browser compatibility verification"
```

## Self-review

Spec coverage: nullable contract, actor preservation, master/native worker controls and frame survival are Task 1; latest-source preservation, independent build, fresh signed payload and bounded live verification are Task 2. All five Review Focus cases have owning checks. No screen feature, Chrome identity override, challenge bypass or production-profile change is included.
