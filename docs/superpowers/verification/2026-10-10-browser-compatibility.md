# WebGPU crash repair verification — 2026-10-10

## Scope and change

Implemented the Cloudflare WebGPU null-safety plan on outer-repo baseline
`b6790033fa` (`cpp-first-exploration`), retaining the latest unrelated changes.
`upstream.sh` remains Firefox 146.0.1, beta.25. The separate TestDome/screen API
plan has not been implemented by this repair.

The ordered patch changes `GPU gpu` to `GPU? gpu` and renames the page and worker
getter declarations/definitions from `Gpu` to `GetGpu`. Both method bodies,
privacy settings, existing actors, secure-context restriction and `[SameObject]`
remain unchanged. The generated Navigator/WorkerNavigator bindings return null
before calling `GetOrCreateDOMReflector`.

## Reproduction and verification

- **Red:** the installed baseline, executable SHA-256
  `54ee08c14f7f59780d83dfe753f793cfe9f2e3d337b68308874874a9db0923ba`,
  passed master-off but failed the disabled blank-frame completion assertion.
  `/tmp/cloakfox-webgpu-before-fix/master-on-disabled-gecko.log:18` records a
  child exiting on signal 11. The captured stack reached DOM wrapping with a
  null WebGPU instance. No installed-app or user-profile changes were made.
- **Build:** `./mach build` succeeded after all five source changes. The initial
  WebIDL-only build failed because nullable getters require `GetGpu`; matching
  page/worker renames resolved it. Build log:
  `/tmp/cloakfox-webgpu-build-20261010.log`.
- **Green:** `probe_webgpu_null_safety.py` passed master-off, master-on-disabled
  and master-on-native-enabled on the bundled development app, signed staging
  app and final mounted DMG. Coverage includes page/blank/srcdoc/navigated
  frames, retained and fresh getters after same-frame navigation, native
  descriptor/receiver behavior, stable native GPU identity and dedicated
  workers. Completion, original-document sentinel and DOM liveness checks
  prevent a null WebDriver response from masking a crash. Final report:
  `/tmp/cloakfox-webgpu-final-probe/result.json`.
- **Existing regressions:** signed staging passed navigator coherence in all
  four containers and worker spoofing (17 worker plus 14 main signals).
  Logs: `/tmp/cloakfox-webgpu-signed-navigator.log` and
  `/tmp/cloakfox-webgpu-signed-workers.log`. `node --test
  tests/fingerprint/test_*.mjs` passed 43 tests; Python probe-scoring tests passed.
- **Reproducibility:** `bash scripts/test-patches.sh` applied all 92 patches to a
  separate extraction, with zero failures. The script cleaned its extraction;
  the current native checkout was never reset. Log:
  `/tmp/cloakfox-webgpu-patch-audit-20261010.log`.

Geckodriver 0.36.0 warned that 0.37.1 is recommended for this Firefox version;
the recorded final probe runs completed successfully.

## Packaging and rulings

The bare `dist/bin/cloakfox` launcher produced mismatched runtime identity and
failed initial GPU/navigator checks. Verification therefore uses the bundled
`dist/Cloakfox.app/Contents/MacOS/cloakfox` and final package executable, which
pass. The launcher discrepancy was not repaired as part of this change.

`./mach package` succeeded but its intermediate app had a stale resource
signature. A separate staging copy had Finder attributes cleared and was
ad-hoc signed; `codesign --verify --deep --strict` succeeds on staging and the
read-only final DMG payload. This is local signing, not notarization.

Final artifact: `cloakfox-146.0.1-beta.25-webgpu-crash-fix-20261010.dmg`.
Application BuildID: `20261010182521`.

| Payload | SHA-256 |
| --- | --- |
| Final DMG | `54db315905b93a5425ac461f5d458bac56a864e7211e807fecd0966d51e89925` |
| Mounted executable | `fbcfd5d22866fd9abe6831fe5c7ebe1fae6c02e51fa324ef0e34e124620629f5` |
| Mounted XUL | `e4966014abe3409aad03e42dc134dc5610cae7d035049d45056c9aa496797c1a` |

Mounted executable and XUL hashes exactly match signed staging. Old DMGs and
`/Applications/Cloakfox.app` were preserved.

## Live outcome

Read-only headful checks used the signed staging app, disposable profiles,
Firefox identity and privacy master enabled. Treet loaded its product listings
and remained alive for the bounded observation. The user-supplied Capital One
link displayed Cloudflare's normal **Verify you are human** checkbox instead of
the broken-frame face; its native log contains no signal-11/EXC_BAD_ACCESS crash.
Challenge completion was not tested: no CAPTCHA was clicked, no login was
performed and no assessment was started.

Screenshots and reports:
`/tmp/cloakfox-webgpu-live-20261010/fixed-treet.png`,
`/tmp/cloakfox-webgpu-live-20261010/fixed-treet-result.json`,
`/tmp/cloakfox-webgpu-live-20261010/fixed-cloudflare.png`, and
`/tmp/cloakfox-webgpu-live-20261010/fixed-cloudflare-result.json`.
These scratch artifacts are local evidence, not committed fixtures.

A separate read-only reviewer found no blocking or actionable correctness
issues in the native patch and regression coverage. Packaging and live results
were reviewed from the verification evidence rather than independently rerun.

## Follow-up: challenge restarts after a human click

The user subsequently reported that clicking the checkbox restarts verification.
Diagnostic runs of the same signed staging app reproduced a fresh challenge
without any content-process signal/EXC_BAD_ACCESS crash. The human performed
the checkbox interaction; the agent only collected browser observations.

The first capture showed an HTTP 200 challenge POST with Set-Cookie, saved
`cf_clearance` cookies, then HTTP 403 on the original link with a new Ray ID.
The second capture additionally confirmed that the subsequent original-link
GET sent `cf_clearance` and `cf_chl_rc_ni`. Its HTTP User-Agent was stable across
the challenge and reload and matched the page's navigator User-Agent. Cookie
values, challenge tokens and the private link are not included in this record.

This rules out the repaired WebGPU crash, a missing saved/sent clearance cookie,
and a changing HTTP User-Agent for these observed runs. It does not establish
why the site's challenge platform rejects/re-challenges the session. No new
browser patch or privacy exception has been justified or applied; successful
challenge passage remains unresolved. Selenium-driven diagnostics can themselves
influence a challenge decision and are not a clean daily-use-browser control.

Local reports: `/tmp/cloakfox-cloudflare-loop-20261010/result.json` and
`/tmp/cloakfox-cloudflare-loop-headers-20261010/result.json`. The latter contains
only cookie names/attributes and request metadata, not cookie values. Console
messages in scratch reports may contain private URLs; do not publish them raw.

## Native-session comparison isolates an automation-associated loop

A normal CLI launch of the signed fixed app, without Selenium, geckodriver or
Marionette, reached the CodeSignal login page with the privacy master enabled.
A second, fresh native profile also passed after one authorized checkbox click:
the original-link response was HTTP 302 to CodeSignal, and the native
accessibility tree showed **Welcome to CodeSignal / Log in to access this page**.
No sign-in or assessment was performed.

For a controlled comparison, `prefs.js` and `user.js` from that passing native
profile were copied into a fresh disposable Selenium profile, excluding cookies
and other site state. Both runs used the same diagnostic app and the same
`cloakfox.s.cloak_cfg_0` configuration (SHA-256 of sorted JSON:
`15d00dd11beb8d7d0b766d5dbc50557ac930f8ba128cee702407ad88573cd2d2`),
including the same Linux Firefox UA. Both retained `cloakfox.enabled=true` in
`user.js`. After an authorized checkbox click, the Selenium session saved and
sent `cf_clearance` but again received HTTP 403 with a new challenge. Its UI
explicitly reported remote control by Marionette. No privacy exceptions or
automation-detection overrides were applied.

This isolates a reproducible automation-associated failure in the diagnostic
environment; it does not reveal Cloudflare's private decision logic.
[Cloudflare's supported-browser documentation](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/)
explicitly excludes Selenium/automation frameworks from production challenge
solving. Native challenge passage is now verified for the fixed payload with
privacy enabled; the automation result must not be treated as native failure.

The user's running Firefox-appearance copy and `/Applications/Cloakfox.app`
both still report BuildID `20261010162253`; the running appearance marker points
to `/Applications/Cloakfox.app`. They predate the fixed `20261010182521` payload.
They were not replaced, restarted or modified during diagnosis. To use the fix,
install the new DMG and launch the updated original Cloakfox app after quitting
the old appearance instance; the appearance manager compares source fingerprints
when preparing its copy and rebuilds it from the updated source.

Native logs: `/tmp/cloakfox-cf-native-20261010/cloakfox-on-clean/`.
Matched Selenium report:
`/tmp/cloakfox-cf-native-20261010/selenium-same-persona/result.json`.
The local diagnostic clone uses a distinct bundle ID solely so the native UI
tool can select it among concurrent browser processes. Its engine/settings are
otherwise the fixed app's; both comparison runs used that same clone.

## Follow-up: the user's Chrome identity overrides also reproduce the loop

The clean native comparison above did not cover the user's manual identity
overrides. Copying only the user's `cloakfox.*` preferences into a disposable
native profile reproduced repeated HTTP 403 challenges with the fixed engine,
without Selenium. The profile advertised Chrome 120 through navigator and HTTP
User-Agent overrides while running Gecko. No cookies, history or credentials
were copied.

In another disposable profile with those same preferences, the settings UI reset
only `navigator.userAgent`, `navigator.appVersion` and `headers.User-Agent` to
the existing Firefox persona. The privacy master remained enabled, the persona
seed was retained, and the unrelated Math override remained. After one authorized
checkbox click, the link returned HTTP 302 to CodeSignal and the native UI showed
**Welcome to CodeSignal / Log in to access this page**. Comparing the cached
persona configurations before/after showed only the navigator and HTTP
User-Agent keys changed: the old cached appVersion was already Firefox even
though its stored manual override differed. This establishes a reproducible
identity-override-associated failure for these settings, in addition to the
separate automation-associated failure. It does not establish Cloudflare's
private rejection reason.

Removing override preferences offline alone was an invalid control because the
valid cached `cloakfox.s.cloak_cfg_0` retained the old values. Resetting them
through the settings UI rebuilt the configuration correctly.

After the user installed/launched the fixed DMG, `/Applications/Cloakfox.app`
reported BuildID `20261010182521`, but the already-running Firefox appearance
copy still reported `20261010162253`. The three Default-container identity
overrides were backed up locally, then reset through that user's settings UI.
The old appearance window was closed and the updated original app launched
against the same existing profile so its appearance copy could refresh. Privacy
protection was retained. No challenge scripts, tokens or detection mechanisms
were modified, and no sign-in or assessment was performed.

The restarted user appearance copy reported BuildID `20261010182521`; its
application.ini and XUL hashes matched the signed fixed staging payload. The
actual profile retained `cloakfox.enabled=true` and
`navigator:webgpu:disabled=true`, with matching Firefox navigator/HTTP UAs.
On the same supplied link, the page first offered a verification-start button,
then the normal checkbox. After the authorized interaction it left Cloudflare
and reached CodeSignal, displaying **Assessment not found**. Thus actual-profile
challenge passage is verified; the destination's assessment error remains
separate and was not investigated by starting or submitting an assessment.

Native failing and passing logs are in
`/tmp/cloakfox-cf-native-20261010/native-user-config/` and
`/tmp/cloakfox-cf-native-20261010/native-user-config-reset/` respectively.
Private links, cookie values and identity seeds are omitted from this record.

## Identity mismatch investigation

The failing native Chrome profile's cached configuration claimed Chrome 120
in both User-Agent fields but still contained Firefox 146 in
`navigator.appVersion`. A fresh native disposable control changed only the
appVersion configuration key to match that Chrome UA. It still returned HTTP
403 after the authorized checkbox click, presented a new Ray ID/checkbox, and
did not redirect to CodeSignal. Thus the appVersion contradiction is real but
correcting it alone did not resolve the loop.

The native failing control's browser console also recorded warnings from the
Cloudflare challenge script for access to `InstallTrigger`, `Window.fullScreen`,
`onmozfullscreenchange`, `onmozfullscreenerror`, and
`WEBGL_debug_renderer_info`. These observations establish accessed APIs, not
their purpose, uploaded values or weight in a rejection decision. WebGL context
loss warnings also appeared in passing runs and do not independently explain
the failure.

The HTTP profile preferences are another distinction outside the cached persona
JSON: both Chrome runs used `h2_profile=chrome`, while the passing Firefox run
used `h2_profile=firefox`; all three used `h3_profile=0`. The settings UI derives
these preferences from the chosen UA. The engine retains Gecko/SpiderMonkey and
NSS TLS, so a Chrome UA cannot provide an actual Chrome implementation. Neither
the exact TLS fingerprint sent nor the site's server-side rejection rule has
been established by this investigation. Cloudflare documents client-side,
header/session and TLS fingerprint signals, but that does not prove this site
used any particular one.

The redacted local control report is
`/tmp/cloakfox-cf-native-20261010/native-user-config-chrome-appversion/redacted-result.json`.
The user's restored, passing Firefox profile was not changed by this control.

## Native screen-management delivery — 2026-10-10

Implemented the separate native screen-management plan on this branch. The
feature is off by default and requires the privacy master, explicit feature
toggle, an owning desktop Chrome/Chromium/Edge identity, and an exact HTTPS
origin in the editable list. Count is configurable from 1–8 and snapshotted
when each inner window is created. Native bindings, frozen object identity,
owner/container presentation, live invocation checks, inactive-frame rejection,
virtual permission snapshots, and modern/legacy/iframe denial are implemented.
The helper and WebIDL use native Gecko objects; no missing-API page shim was added.

### Test evidence

- **RED → GREEN:** the original native build lacked all four screen surfaces;
  first-script API and Settings/presentation tests now pass. Additional RED
  regressions caught a wrong-typed saved-origin value, portrait letterbox angle,
  and Window-method initialization before document attachment. The fixes pass.
- **Permission RED → GREEN:** Task 2 rejected the permission name with TypeError
  and resolved a call despite modern empty-list denial. Task 3 passes exact
  empty-list parsing, spacing/dictionaries, malformed/lookalike/nonempty
  controls, inherited and iframe/legacy denial, workers denied, live gate
  changes, query snapshots and permission privacy enabled.
- **Final dev build:** Settings, presentation, API/policy, media permission,
  UA Client Hints (67 checks), worker identity, navigator coherence (four
  containers), and WebGPU null-safety pass. Logs are
  `/tmp/cloakfox-screen-task3-*.log`,
  `/tmp/cloakfox-screen-dev-navigator_coherence.log`, and
  `/tmp/cloakfox-screen-dev-webgpu_null_safety.log`.
- **Synthetic recording:** the deliberately empty-output guard fails. The real
  headful fixture selects the observed no-preference VP8 fallback, using both
  VideoEncoder and MediaRecorder capability checks. Dev output is 4,490 screen
  bytes and 7,742 webcam/audio bytes; mounted output is 4,331 and 6,404 bytes.
  All four blobs have EBML `[26,69,223,163]`; sources and AudioContexts are
  stopped/closed. Reports: `/tmp/cloakfox-screen-dev-recording/recording.json`
  and `/tmp/cloakfox-screen-mounted-testdome_recording/recording.json`.
- **Mounted payload:** Settings, presentation, API/policy, synthetic recording
  and WebGPU null-safety pass on the read-only DMG application, with disposable
  profiles. Logs: `/tmp/cloakfox-screen-mounted-*.log`.
- **Reproducibility:** all 95 ordered patches apply to fresh Firefox 146.0.1
  source. Before the audit script's cleanup, a test-only shell hook retained
  the 30 files touched by these three patches; every SHA-256 matches the
  compiled checkout. Reports: `/tmp/cloakfox-screen-patch-audit.log` and
  `/tmp/cloakfox-screen-verification/patch-input-comparison.json`.

### Signed artifact

`./mach build` and `./mach package` succeeded. The intermediate packaged app
had a stale resource signature; a separate staging copy was ad-hoc signed.
Both staging and the read-only mounted app pass `codesign --verify --deep
--strict`. This is local signing, not notarization. Mounted executable and XUL
hashes match signed staging. The installed app, real profiles, and previous
DMGs were preserved.

Artifact: `cloakfox-146.0.1-beta.25-browser-compat-20261010.dmg`.
BuildID: `20261010204436`.

| Payload | SHA-256 |
| --- | --- |
| Final DMG | `2b696369c94b0f437dd63a7399e5c4ae513e6893fddb8f0e58ed90f38fbf438e` |
| Mounted executable | `7f598d42d7107ae0b5533faa10c11c5e791855385ef0cbf80e422530bdb36d4a` |
| Mounted XUL | `261e45fc39bdc24409ab2273eefb9f709859897228f3b1277f6bd14d9aeb1335` |

### Read-only live result and limits

The supplied TestDome start-test link was checked in the mounted payload. A
privileged, test-profile-only document observer recorded the native surfaces
before page scripts: Chromium had getScreenDetails/ScreenDetails/ScreenDetailed
and isExtended; Firefox had none. The Chromium page reached **Detect Screens**
without the getScreenDetails compatibility warning. Its query was granted and
the API returned one frozen virtual screen. The Firefox control queried denied
and displayed the missing API/browser recommendation.

No Detect Screens, Next, device-sharing, or Start the Test control was clicked;
no assessment began and no real device capture was approved. Local APIs and
synthetic encoding are verified. Physical webcam/screen capture, remote media
delivery and full assessment support remain unverified. The unrelated live
Cloudflare outcome remains the independently documented result above.

Local evidence: `/tmp/cloakfox-screen-live/result.json`, `chromium.png` and
`firefox.png`. Invitation URLs/candidate data are not committed.

### Implementation rulings and costs

- Ruling: Keep existing feature branch/native checkout instead of a fresh worktree — the approved plan explicitly preserves this patched source/build cache; no main/master work or user-profile changes. Cost if wrong: source isolation is weaker; snapshots/ordered patches and explicit staging preserve unrelated changes.
- Task 1: Ruling: local 443/80 sockets are denied by macOS for this process — fixture uses ephemeral loopback TLS/HTTP ports and explicitly lists its canonical TLS origin; production default remains tested in Settings. Cost: local navigation cannot directly exercise the production default-port route.
- Task 1: Ruling: macOS standalone dist/bin executable fails XPCOM loading — native probes use the same build's dist/Cloakfox.app after ad-hoc signing. Cost: app packaging paths also influence the dev probe; final mounted-payload probes still validate distribution independently.
- Task 2: Ruling: spec's no-own-getScreenDetails expectation contradicts native Gecko Window binding placement (baseline alert/requestAnimationFrame are own properties; Window.prototype.alert is undefined). Preserve generated native placement and compare it with alert, rather than altering the binding generator or adding a JS shim. Cost: shallow own-property checks cannot distinguish this native API from a shim; native descriptors/receivers/brands/function text supply the other checks.
- Task 2: Ruling: Gecko denies unknown policy features (DefaultAllowListFeature returns eNone), so the planned Task 2 invocation check cannot pass before Task 3's feature registration. Move only window-management/eSelf registration into Task 2; keep native permission integration and modern header parsing in Task 3. Cost: legacy/iframe policy support lands one commit earlier; final scope and denial behavior are unchanged.
- Task 2: Ruling: IMPL_EVENT_HANDLER requires global static atoms absent for these two events. Use EventTarget's existing string/dynamic-atom GetEventHandler and native atom SetEventHandler overloads for the two generated WebIDL accessors, preserving listener semantics without adding unrelated global HTML event names. Cost: a small atom lookup on handler access instead of a static atom pointer.
- Task 2: Ruling: native ScreenDetails name collides with existing DOMTypes IPDL transport class — map WebIDL ScreenDetails to CloakfoxScreenDetails in Bindings.conf; mark Screen concrete after adding its derived interface so the existing nsScreen wrapper remains generated. Cost: a small explicit binding mapping replaces the plan’s default class mapping; public API names/brands stay unchanged.
- Task 3: Ruling: existing Gecko iframe allow changes affect the next document, not the already loaded document (Task 2 baseline resolved before/after assignment, denied after navigation). Preserve that document-policy lifetime; test changing allow then navigating, while new queries still recheck the current document’s policy/gates. Cost: changing allow alone cannot revoke this loaded document until navigation/reload.
