# Fingerprint tests

## Disabled WebGPU null safety

`probe_webgpu_null_safety.py` checks that the disabled native GPU getter safely
returns null in actor-free blank frames instead of crashing the content process.
It also covers ordinary/srcdoc/navigated realms, retained getters after
navigation, master-off/native-enabled controls and the worker WebGPU binding.
Each read must complete in the original live document; a null WebDriver response
cannot pass as the intended native null value. It uses disposable profiles and
loopback pages, without requesting any GPU adapter/device.

```sh
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  REPORT_DIR=/tmp/cloakfox-webgpu-results \
  python3 tests/fingerprint/probe_webgpu_null_safety.py
```

Set `CLOAKFOX_HEADFUL=1` to inspect the local fixture. Run against the final
packaged app as well as the development binary to detect a stale XUL payload.

## Website appearance

Firefox Settings → General → Website appearance supports **Automatic**, **Light**
and **Dark**, independently of the privacy master switch and container persona.
Automatic follows the browser theme; the system theme follows the OS appearance.
The native `layout.css.prefers-color-scheme.content-override` preference uses
0 = Dark, 1 = Light, 2 = Automatic. Fresh profiles default to Automatic and user
choices persist across restarts. Sites must support the corresponding color
scheme for their own appearance to change.

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_website_appearance.py
```

This uses disposable profiles and local same-/cross-origin frames, checks page
JavaScript against native CSS, selects actual built-in themes, and verifies live
MediaQueryList change events without reloading. It tests containers 0 and 2 with
the master on/off, legacy persona overlays, default preferences and persistence
after restart. Simulated OS appearance is confined to the test profile.

## Application appearance (macOS)

In `about:cloakfox`, enable **Firefox appearance**, then click **Apply and
restart**. Turn it off and restart to restore Cloakfox names and icons. The
preference `cloakfox.appearance.firefox` defaults to false and is independent
of the privacy master switch. A restart applies desktop/application names,
icons and Firefox branding; the existing profile and session are retained.
It also changes the bundled extension's toolbar tooltip and extensions-panel
labels, popup title/heading and icons to Firefox. Turning appearance off restores
the original extension UI. Apply the switch from the updated installation to
rebuild any older private appearance copy.

The feature creates a private, locally signed `Firefox.app` copy under the
profile's local `cloakfox-appearance` directory. It requires disk space for an
extra app bundle. The original installation is preserved. The copy lives at
`<local profile>/cloakfox-appearance/Firefox.app` and is reused without resigning
when the source payload is unchanged. Source updates (including loose development
resources) rebuild it at that same path. Launching the original app honors the
saved choice after session restoration. Do not remove or relocate
the original app while using the copy. Linux and Windows controls are disabled.

The signed copy contains a profile binding, so Finder and macOS permission
relaunches select the profile that created it. Explicit `--profile`, `-P`, the
profile manager and restart environment still take precedence. A missing or
invalid binding target opens the profile manager instead of creating a blank
profile. **Show app in Finder** reveals the actual running bundle for macOS
Camera, Microphone and Screen Recording settings. Reusing an unchanged copy
preserves its signature; a software update may still require macOS approval.

If Screen Recording is enabled but sharing is denied after an update, macOS
can retain the previous ad-hoc signature requirement for the same bundle ID.
Adding the updated app while its old row exists may leave that stale requirement
unchanged. In Screen & System Audio Recording, use the Firefox row's **Show in
Finder** menu to verify that it is this appearance copy, remove that row, then
add the app revealed by **about:cloakfox → Show app in Finder**. Complete macOS's
**Quit & Reopen** prompt before retrying sharing. The browser's site prompt and
native screen chooser still require their normal approvals.

This is cosmetic branding: the extension keeps its internal ID, version,
permissions, origin and privileged API. The private copy uses a different
bundled resource root so Gecko reloads its labels and icons in an existing
profile rather than keeping cached branding. The system add-on is hidden from
`about:addons`; its visible labels live in the toolbar/extensions panel.
It does not guarantee indistinguishability from Firefox to
websites, screen sharing, or external monitoring applications. Official image
assets retain their Mozilla license and trademark notice in
`additions/browser/components/cloakfox/appearance/LICENSE`.

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_appearance.py
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_appearance_restart.py
CLOAKFOX_XPCSHELL=/path/to/dist/bin/xpcshell \
  python tests/fingerprint/probe_appearance_profile.py
node --test tests/fingerprint/test_appearance_cache.mjs
```

Both use disposable profiles with spaces in their paths. The first checks
bundle metadata, icon payloads, legacy/Fluent branding, setting persistence,
source preservation, signed-copy reuse and canceled restart handling. It
checks loaded extension metadata, toolbar labels, rendered popup branding,
icon assets, plain reopening without profile arguments, and working popup bridge across both directions and with the
privacy master switch off. Run
it against a packaged app as well to cover `omni.ja` rebuilding. The second
uses the actual restart button in both directions and reconnects geckodriver
to check profile, tab and extension/browser branding preservation, then launches the original
app again to verify the saved appearance. Set `CLOAKFOX_HEADFUL=1` on the second
probe to check macOS's application name and bundle identity during the handoff.
Use an app under `/Applications` or a materialized test copy under `/tmp` for
that probe; launching a development bundle under Documents via macOS Launch
Services may require a system folder-access prompt.

The native profile probe runs seven startup-selection cases against isolated
profile databases. The cache tests cover sealed and loose source updates,
concurrent preparation, failed signing, replacement rollback, damaged cached
copies and protection of the running bundle.

## Page-visible identifier audit

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_identifier_leaks.py
```

Uses local HTTP pages and disposable profiles. Compares a master-disabled
native baseline with masking enabled in containers 0 and 2, collecting from
the main page, same-/cross-origin frames, dedicated/shared/service workers.
Checks product strings in navigator/global/DOM/storage surfaces, exception
stacks and filenames, function names/arity/native source, property sets and
flags, getters, and non-constructor semantics. Property sets are sorted because
this audit does not assert lazy property-resolution order. It also checks that
ordinary privileged exports retain their constructor default and that naming
an exported function does not stamp a new global.

Worker Math uses native C++ functions with GC-traced private slots rather than
an evaluated wrapper script. This removes the `CloakfoxWorker.js` error filename
and leaves `Function.prototype.toString` native. The existing deterministic
noise, container seed, integer/non-finite results and negative zero are kept.
Actor exports opt into a native internal name and non-constructor behavior;
the privileged export defaults used elsewhere remain unchanged.

The audit requires the Math layer to run in every realm, including remote
service workers. It compares exact IEEE-754 bits for all 23 wrapped methods,
checks distinct container seeds and an explicit seed override, toggles the
master switch on both initially-disabled and already-masked live pages/workers,
changes their configuration while they remain running, and recreates realms after
configuration changes (including seed 0, which disables Math noise). Exact bits
avoid WebDriver's numeric serialization rounding obscuring hash inputs.

`cloakfox-worker-config-cache.patch` caches the authoritative cpp-first overlay
on the main thread before workers start. `cloakfox-live-worker-math.patch`
delivers later overlay changes/removal through the existing parent-to-content
preference channel, including remote service-worker processes. The main thread
parses and caches the Math seed under a mutex; worker calls read the typed seed
without JSON parsing or IPC. The page actor reads the live shared-data overlay
and parses it only when the configuration text changes.

Math method wrappers are installed before page/worker scripts even with the
master disabled; their results stay native while disabled or when the seed is
zero/missing/invalid. Enabling and seed regeneration apply to existing realms,
including captured Math references, without navigation or worker termination.
The live checks preserve each realm's token, increasing message counter and
function identity, cover same-/cross-origin frames and all worker types, and
verify an update in container 2 leaves container 0 unchanged. Removal and
malformed/invalid seed data clear a previously cached seed. Updates propagate
asynchronously through normal browser process messaging.

This probe does not establish that the browser is indistinguishable from stock
Firefox across all APIs or fingerprints. Set `IDENTIFIER_PROBE_REPORT` to change
its JSON path.

## Window and tab activity masking

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_focus_masking.py
```

The opt-in **Mask window and tab activity** setting in `about:cloakfox` is
`cloakfox.opt.focus_masking` (default false). The master `cloakfox.enabled`
switch also disables it. It applies to all containers and takes effect on open
pages: web content sees `hasFocus()=true`, `hidden=false`, and
`visibilityState="visible"`. Window/document focus events and element events
caused by native deactivation/reactivation are private; ordinary field-to-field
focus, typing, shadow-root retargeting and browser chrome retain native behavior.
CSS focus state follows the last logically focused element while away.

Native mouse/pointer departures from the web-content surface and corresponding
return boundary events are private, including same- and cross-origin frames.
Movement between elements or between an iframe and its parent keeps normal
`out`/`leave`/`over`/`enter` events. CSS `:hover` and the corresponding styles
retain the last hovered chain during a masked departure. Returning elsewhere
reconciles the old frame; disabling the option or master switch clears retained
hover immediately. Normal element movement, clicks, pointer capture, touch
cancellation and script-dispatched events retain native behavior.
This does not fabricate input or conceal elapsed time without editor activity.
Firefox's Idle Detection API is not implemented: `IdleDetector` remains absent
in pages and dedicated workers regardless of the activity option/master switch.

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_pointer_activity.py
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_background_activity.py
```

Both probes run headful against disposable profiles and local servers.
The pointer probe uses Gecko's privileged native mouse test API; unmasked
controls must observe departures/returns before masked results count. It also
checks CSS hover/visual styles, frame transitions, returns elsewhere, live
switches, pointer capture and IdleDetector absence. Set
`POINTER_PROBE_REPORT` to change its JSON output path. Set
`POINTER_PROBE_INPUT=widget` for a headless Gecko widget/APZ input run; that
mode verifies the trusted Gecko/IPC path without OS mouse delivery and does
not replace the default desktop native-input check.
The native path sends a second move at the same position to settle macOS/APZ
ancestor routing into nested frames. It requires the intended element to be
hovered before asserting departure masking; presses and releases are sent once.
The background probe measures server receive times for HTTP and WebSocket
heartbeats, rAF, page timers and dedicated-worker timers through tab switching,
minimization and native window deactivation. Its default 35-second background
run exceeds Gecko's normal throttling startup delay without changing scheduling
preferences. Set `BACKGROUND_PROBE_SECONDS` to change that duration and
`BACKGROUND_PROBE_REPORT` to change its JSON output path. It requires the Python
`websockets` package in addition to Selenium. Connectivity and callback
scheduling are tested; OS sleep, network outages and application-defined
inactivity reports are outside this setting's control.

Fullscreen reporting presents a logical fullscreen view: `document.fullscreen`,
`mozFullScreen` and `window.fullScreen` are true even when the real window is
windowed. A document without native DOM fullscreen reports its root element
through `fullscreenElement` and `mozFullScreenElement`; the root matches CSS
`:fullscreen`. Real fullscreen targets retain their normal getters, shadow-root
retargeting and CSS state. Shadow roots without a real fullscreen target remain
null. Fullscreen change notifications are private. Real entry/exit, permission
and activation checks, rejection promises and fullscreen errors remain native.
Browser chrome retains actual state. Sites comparing element identity or window
geometry can still observe differences; screen capture is unaffected.

`probe_fullscreen_gate.py` checks a local DOM fullscreen gate before entry and
after real exit, including aliases, CSS, shadow DOM and live option/master
switches. Native DOM fullscreen uses Gecko's widget-ignore test mode rather than
macOS fullscreen animation. Set `FULLSCREEN_PROBE_REPORT` for a JSON evidence
path (default `/tmp/cloakfox-fullscreen-gate-results.json`).

Background page/worker timers follow foreground policy; animation callbacks
use the same software refresh timer in both foreground and background. This
can increase CPU/battery use. Navigation, detached documents, BFCache suspension,
screen capture and monitoring by external applications are not concealed.
This setting does not guarantee that activity cannot be inferred.

The probe uses disposable profiles and local HTTP pages. Background pages report
their observations to the local server without selecting/refocusing the tab.
It checks same/cross-origin frames, ordinary element events and typing,
fullscreen reporting, background scheduling and live option/master switches.
Use `CLOAKFOX_HEADFUL=1` to exercise native window activation, minimization and
DOM fullscreen on a desktop. The fullscreen test uses Gecko's
`full-screen-api.ignore-widgets` test mode to avoid OS transition timing; native
OS fullscreen entry is not covered. Window activation and minimization use real
windows. Rebuild the native patch before running it; a settings file change
alone cannot update an existing XUL binary.

### Monaco / Firepad-X focus integration

`probe_monaco_focus.py` exercises the published `@hackerrank/firepad@0.8.6`
Monaco adapter with its declared peer version, `monaco-editor@0.18.1`. It loads
local assets and instantiates the actual adapter; it does not connect to Firebase
or an assessment platform. This does not establish which versions production
assessment sites currently deploy.

```bash
monaco_probe_assets=$(mktemp -d -t cloakfox-monaco)
npm install --prefix "$monaco_probe_assets" --ignore-scripts --no-audit --no-fund \
  --legacy-peer-deps @hackerrank/firepad@0.8.6 monaco-editor@0.18.1 esbuild@0.25.12
MONACO_PROBE_ASSETS="$monaco_probe_assets" CLOAKFOX_HEADFUL=1 \
  CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_monaco_focus.py
```

The probe bundles the unmodified adapter against the page's Monaco instance.
It checks editor-widget, editor-text, and adapter callbacks with masking off/on
during tab departure/return, native window activation, and minimize/restore.
It also checks ordinary field focus, explicit blur/focus, and typing/model
updates. Reports come from the page to a local server, without refocusing the
background editor. Baseline minimization callbacks are recorded as observations:
macOS can minimize a window without generating editor blur/focus events.
`MONACO_PROBE_REPORT` selects the JSON evidence path; the default is
`/tmp/cloakfox-monaco-focus-results.json`.

## Clipboard signal masking

Enable **Mask clipboard signals** under Optional hardening in `about:cloakfox`.
`cloakfox.opt.clipboard_masking` defaults to false, applies to all containers,
and takes effect on open pages. The master `cloakfox.enabled` switch disables it.
This is independent of **Disable clipboard API**, which controls
`navigator.clipboard` access.

Web listeners do not receive trusted copy/cut/paste events or conventional
clipboard shortcut key events. Paste `beforeinput`/`input` report `insertText`
and no DataTransfer; cut reports `deleteContentBackward`. Native clipboard
editing, browser chrome, ordinary typing and script-created events retain
their behavior. Pages still see inserted text, text changes, selections and
input timing, so this does not make clipboard use or keystrokes undetectable.

This strict mode can break editors or copy buttons that depend on clipboard
event handlers, including editors that maintain their own document model.
Disable it for those sites.

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_clipboard_masking.py
```

The probe uses a disposable headless profile and process-local clipboard;
it does not modify the desktop clipboard. It checks native paste/copy/cut,
clipboard shortcuts, input metadata, contenteditable, same/cross-origin
frames, containers, synthetic events, zero-keyCode trusted keypress,
browser chrome, undo/redo, custom-editor compatibility and live settings.

## Letterboxing / native window geometry

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_letterboxing.py
```

Uses a disposable profile and local HTTP pages. Checks responsive browser chrome,
shared viewport buckets, JavaScript/CSS/screen/visual-viewport agreement, same-
and cross-origin frames, multiple containers, scroll offsets, reload/navigation,
cursor default, and live master/letterboxing switches. `GECKODRIVER` may specify the driver binary;
otherwise it must be on PATH. The probe asserts that Cloakfox actually launched.

Letterboxing is enabled by default independently of global RFP (which stays off).
While enabled, native geometry ignores saved persona viewport/screen dimensions:
the actual content viewport drives layout and the protected screen dimensions.
The tabs and toolbar retain Firefox's normal flexible sizing. Disabling
`privacy.resistFingerprinting.letterboxing` restores legacy persona geometry,
but never restores the physical browser-window size hijack.

Two tools for validating the H2/H3 transport-fingerprint patches land as
designed and match the browser they claim to mimic.

## 1. `test_h2_profile.py` — automated shape check

Launches the built Cloakfox binary under each H2 profile (firefox / chrome /
safari) via **Selenium + geckodriver**, hits `https://tls.peet.ws/api/all`,
and asserts the SETTINGS frame, WINDOW_UPDATE, and HPACK pseudo-header order
match each profile's spec.

### Why Selenium and not Playwright

Playwright's Firefox driver uses the Juggler protocol, which requires a
Juggler-patched Firefox binary. Playwright ships one; Cloakfox does not.
Attempting `playwright.firefox.launch_persistent_context(executable_path=CLOAKFOX_BIN)`
times out after 180s waiting for a Juggler handshake that never comes.

geckodriver speaks Marionette — the WebDriver protocol that every Firefox
build (vanilla, LibreWolf, Cloakfox, Camoufox) supports by default. No patch
required.

### Setup

```bash
pip install pytest selenium
brew install geckodriver          # macOS
# or download geckodriver from https://github.com/mozilla/geckodriver/releases
```

For native XUL-only edits on macOS, use `make relink` before launching an app
bundle or packaging it. `mach build binaries` updates `dist/bin/XUL` but leaves
the development `.app` copy stale, and `mach package` consumes that app copy.
Use a full `make build` when changing other native executables or libraries.
JS-only actor edits follow the loose-file workflow documented in `CLAUDE.md`.

### Run

```bash
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

On Linux, point at the built-in-tree binary:

```bash
CLOAKFOX_BIN=$(pwd)/firefox-src/obj-x86_64-pc-linux-gnu/dist/bin/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

Skips cleanly when `CLOAKFOX_BIN` is unset — CI can run the test suite
without blowing up on machines without a built binary.

### What each test checks

- `test_h2_profile_shape[firefox]` — SETTINGS {1,2,4,5}, HPACK order `:method, :path, :authority, :scheme`.
- `test_h2_profile_shape[chrome]` — SETTINGS {1,2,3,4,6} with MAX_CONCURRENT=1000, INITIAL_WINDOW=6291456, MAX_HEADER_LIST=262144; WINDOW_UPDATE=15663105; HPACK order `:method, :authority, :scheme, :path`.
- `test_h2_profile_shape[safari]` — sparse SETTINGS {2,3,4} with MAX_CONCURRENT=100, INITIAL_WINDOW=2097152; WINDOW_UPDATE=10485760; HPACK order `:method, :scheme, :path, :authority`.
- `test_h2_profiles_produce_distinct_fingerprints` — all three profiles produce distinct `akamai_fingerprint_hash` values. Collapsing hashes mean the WebIDL setter isn't firing OR `cloakfox.cfg` is clobbering user prefs (see gotcha below).

### One shared probe per session

The three shape tests and the distinct-fingerprints test share a single
session-scoped fixture that launches Cloakfox once per profile. This makes
the full suite run in ~6 seconds against a local build.

### Known limitations

- **Headless is OK** for this test — we only care about wire-level bytes,
  not JS-level MAIN-world spoofing. Tests that check `navigator.*`, canvas,
  etc. would need headful.
- Geckodriver prints its log to `<tmp>/gd-<profile>.log` if you need to
  debug why a launch failed.

### Why the `pref()` vs `defaultPref()` matters (gotcha)

The AutoConfig file `settings/cloakfox.cfg` originally declared:

```
pref("network.http.http2.fingerprint_profile", "firefox");
```

In Mozilla's AutoConfig semantics, `pref()` overwrites the user value on
every startup. So if the extension (or a test, or an about:config edit)
flipped the pref to "chrome", the next startup reset it to "firefox" and
the patch emitted Firefox-default SETTINGS. The test caught this with
`test_h2_profiles_produce_distinct_fingerprints` failing — all three
profiles produced identical hashes.

Fix: use `defaultPref()` for toggleable prefs. This only seeds the default
value; the user value (set by `Preferences::SetCString` via the WebIDL
setter, or by `set_preference` in the test) survives restart.

## 2. `mitm_h2_observer.py` — local packet-level observation

A mitmproxy addon that prints the exact H2 SETTINGS frame, WINDOW_UPDATE
value, and HPACK pseudo-header order Cloakfox emits per connection. Use
when you want to see bytes on the wire, not a remote service's interpretation.

### Setup

```bash
pip install mitmproxy  # 10+ required for H2 introspection
```

### Run

```bash
mitmproxy -s tests/fingerprint/mitm_h2_observer.py --listen-port 8080
```

Then in Cloakfox, `about:config`:

```
network.proxy.type                 = 1
network.proxy.http                 = 127.0.0.1
network.proxy.http_port            = 8080
network.proxy.ssl                  = 127.0.0.1
network.proxy.ssl_port             = 8080
network.proxy.share_proxy_settings = true
```

Visit any `https://` site that speaks H2. mitmproxy prints a block per new
connection:

```
─── 192.0.2.1:443 ──────────────────────────────────────
SETTINGS:
  HEADER_TABLE_SIZE          (1) = 65536
  ENABLE_PUSH                (2) = 0
  MAX_CONCURRENT             (3) = 1000
  INITIAL_WINDOW_SIZE        (4) = 6291456
  MAX_HEADER_LIST_SIZE       (6) = 262144
WINDOW_UPDATE: 15663105
HPACK order on first HEADERS: :method, :authority, :scheme, :path
```

### HTTPS interception note

mitmproxy intercepts TLS by injecting its own CA cert. Install mitmproxy's
cert (`http://mitm.it/` from a proxied browser) so Cloakfox trusts the
intercepted connections. This is pure local observation — nothing about
the cert manipulation leaks the real fingerprint.

## What lives where

```
tests/fingerprint/
├── README.md                — this file
├── test_h2_profile.py       — Selenium E2E: launches Cloakfox, hits peetwapp
└── mitm_h2_observer.py      — mitmproxy addon: logs H2 frames locally
```

## Live verification output (reference)

Run against a build at `unified-maskconfig@2195549a9c`:

```
firefox: 6ea73faa8fc5aac76bded7bd238f6433 | 1:65536;2:0;4:131072;5:16384 | WU=12517377 | m,p,a,s
chrome : a345a694846ad9f6c97bcc3c75adbe26 | 1:65536;2:0;3:1000;4:6291456;6:262144 | WU=15663105 | m,a,s,p
safari : c9da4b13f7b57d7e7082044bd0f7225c | 2:0;3:100;4:2097152 | WU=10485760 | m,s,p,a

============================ 4 passed in 6.29s ============================
```

## 3. `test_h3_profile.py` — H3 profile pref plumbing

Verifies the HTTP/3 fingerprint profile pref round-trips through Firefox's
static_prefs system. Wire-level observation of the QUIC SETTINGS frame
would need mitmproxy-quic / wireshark — out of scope here. Instead this
test proves: (a) the default pref is 0, (b) setting via prefs.js survives
browser startup (defaultPref contract), (c) the `setHttp3Profile` WebIDL
method is bound on windows.

Documents a known limitation in its header — the WebIDL setter's
`Preferences::SetUint` call runs in content-process scope and doesn't
persist to the parent prefs DB without IPC. Selenium/prefs.js is the
working path today; a WebExtensions Experiment API is the follow-up.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_h3_profile.py -v
```

## 4. `test_sec_ch_ua.py` — Sec-CH-UA HTTP header injection

Checks the webRequest header-spoofer emits `Sec-CH-UA`, `Sec-CH-UA-Mobile`,
`Sec-CH-UA-Platform` headers when the assigned profile is Chromium, and
does NOT emit them for Firefox/Safari profiles. Documents the cold-start
race: first navigation in a session can't have CH headers because the
inject script hasn't posted the active profile yet.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_sec_ch_ua.py -v
```

## 5. `test_math_constants.py` — Math.PI / Math.E / etc. determinism

Four tests: perturbation (not IEEE), in-session determinism, cross-domain
differentiation, Math.sin is noisy too. Uses DOM-injection pattern because
selenium's `execute_script` sandbox maintains a separate `Math` binding
from the page's.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_math_constants.py -v
```

## 6. `antibot_battery.py` — pre-release validation tool (not pytest)

Drives Cloakfox through bot.sannysoft / areyouheadless / browserleaks /
CreepJS under each of the three transport profiles, captures full-page
screenshots, extracts verdicts where possible, emits a markdown report.
Not wired into pytest — runs for minutes and depends on external sites.

```bash
CLOAKFOX_BIN=... python tests/fingerprint/antibot_battery.py
```

Output at `tests/fingerprint/reports/<timestamp>/REPORT.md` with inline
screenshots.

## Gotchas we hit (and documented in tests)

Writing these tests surfaced several real bugs in the shipped build,
each worth remembering:

1. **`jar.mn` paths must match `manifest.json`.** Previously the jar
   packaged files under `dist/inject/index.js` but manifest said
   `inject/index.js` — Firefox silently skipped registering the content
   script and no JS-level spoofing ran in ANY shipped build. Fixed by
   flattening the `dist/` prefix from jar.mn destinations.

2. **AutoConfig `pref()` clobbers user values.** `cloakfox.cfg` was
   using `pref()` for the H2/H3 fingerprint toggles, which in Mozilla
   AutoConfig semantics overwrites the user pref on every startup.
   Must use `defaultPref()` so user values (set via selenium, extension,
   or about:config) survive restart.

3. **Math.PI is non-writable non-configurable per ECMA spec.** You
   can't Proxy-wrap Math and return a different PI — the proxy invariant
   for non-writable non-configurable properties demands the same value.
   Any access throws TypeError. Workaround: build a plain object with
   writable constants and replace `window.Math`.

4. **Double XOR cancels the domain contribution to the seed.** The
   inject script's fallback `generateSeed(domain)` XOR-folded domain
   into the seed, then `initializeSpoofers()` XOR'd the domain in AGAIN
   to derive the page PRNG. Domain bits cancel; every fallback page
   gets the same PRNG. Fixed by dropping the domain from generateSeed
   — let the spoofers module be the only place domain is XOR'd.

5. **Noise must exceed float64 ULP to be visible.** My first Math
   constant spoofer used 1e-15 noise. Math.PI's ULP is ~4.44e-16 — a
   1e-15 perturbation rounds to zero half the time, producing IEEE-
   identical bit patterns and defeating the spoof. Bumped to 1e-13
   (~225 ULPs — guaranteed visible, still invisible numerically).

6. **WebIDL setters from content process don't persist prefs.**
   `Preferences::SetCString/SetUint` called from a WebIDL method runs
   in content-process scope. In e10s Firefox the parent owns the prefs
   DB; content writes don't persist without IPC. The `setHttp2Profile`
   / `setHttp3Profile` methods self-destruct (proving they were called)
   but the pref doesn't actually change. Real toggle path is via
   profile prefs.js or about:config — not the page-script setter.

7. **Selenium sandbox has its own Math binding.** `driver.execute_script`
   runs in a webdriver sandbox with a separate copy of Math from the
   page. Reading `Math.PI` from selenium gets the IEEE default even when
   the page's Math is spoofed. Workaround: inject a `<script>` tag that
   writes the value to the DOM, then read via `find_element`.

## What lives where

```
tests/fingerprint/
├── README.md                — this file
├── test_h2_profile.py       — H2 SETTINGS/WINDOW_UPDATE/HPACK shape per profile
├── test_h3_profile.py       — H3 pref plumbing
├── test_sec_ch_ua.py        — HTTP header injection
├── test_math_constants.py   — Math.PI/E/LN2 noise
├── mitm_h2_observer.py      — local byte-level observer
└── antibot_battery.py       — manual pre-release validation tool
```

## Bundled-font glyph rendering (macOS desktop)

`probe_bundled_font_rendering.py` displays registered Helvetica, Menlo, Arial
and Times New Roman beside webfonts loaded from the exact bundled files. It
checks text/font readiness and matching reference widths in a content page
and `about:cloakfox`, with the master off/on. Run with `CLOAKFOX_HEADFUL=1`
to inspect the native desktop window; `CLOAKFOX_PREVIEW_SECONDS` controls
the inspection interval (45 seconds per case by default).

Verify `·`, `×`, `—`, `fi`, `ff`, `ffi`, `files`, `offline` and `Graphics`
visually. Ordinary WebDriver screenshots use software rendering and can
pass while the desktop compositor draws wrong or missing glyphs. A headless
pass alone does **not** verify this regression.

## Chromium UA Client Hints compatibility

`probe_user_agent_data.py` uses local pages and disposable profiles to check
`navigator.userAgentData` before the first page script runs, in same-/cross-origin
frames and dedicated/shared/service workers. It exercises the Chromium-brand
predicate used by HackerRank's onboarding dialog, Chrome/Edge versions,
container isolation, Android metadata, native descriptors, frozen brand arrays,
JSON output, requested-hint filtering, and secure-context/master/Firefox gates.

The API is native and follows the selected `navigator.userAgent` override when
Cloakfox is enabled. Chrome/Chromium and Edge identities enable it; reload pages
after changing identity or the master switch. Firefox personas leave it absent.
High-entropy details not established by the UA are empty, including reduced
Mac/Windows OS revisions; the actual host's metadata is never substituted.

This covers the JavaScript Client Hints API. It does not implement HTTP
`Accept-CH` negotiation, Chromium's window-management APIs, or Chromium WebRTC
behavior, and does not establish interview/proctoring compatibility.

## Settings field overrides

`probe_settings_overrides.py` edits the real `about:cloakfox` fields in disposable
profiles with focus/clipboard masking enabled. It checks that saved pins reach
the active config, the container dropdown lists and selects real containers,
and settings reloads, persona regeneration and browser restarts retain edits.
It also verifies a local page receives the edited navigator/HTTP user agents,
hardware concurrency and UA Client Hints, and that individual/all reset actions
restore persona values without affecting another container. Run with
`CLOAKFOX_BIN=/path/to/cloakfox`; optional `REPORT_DIR` saves structured results.

## Locale tag correctness and Settings initialization

`probe_locale_tags.py` checks that explicit German, French, Japanese, Chinese,
Arabic and British English tags retain their language/script/region with the
master on and off. It records the cost of repeated `Intl.Locale.maximize()`
operations and verifies native OS-preference locale overrides clear when removed
or disabled. Firefox caches the JS runtime's default locale separately; the probe
reports it but does not claim live `Intl.DateTimeFormat()` default updates from
changing only Cloakfox config. Run with `CLOAKFOX_BIN` and optional `REPORT_DIR`.

## Math animation hot path

`node --test tests/fingerprint/test_math_seed_cache.mjs` drives the real Math
actor with a SharedMap fixture that returns a fresh clone on each read. It checks
that repeated operations and multiple windows deserialize once per published
snapshot, while captured functions still receive live seeds/master updates and
removed or invalid seeds clear noise. It also checks numeric calls avoid repeated
preference reads and a second realm crossing, while coercion keeps the original
page function. Sin/cos/tan preserve the page realm when the fdlibm global policy
is false, including after live policy changes.

Logarithms (`log`, `log2`, `log10`, `log1p`) and `pow` retain native values
in pages and workers by default. Firebase uses truncated log ratios to build its children
trees and powers to hash numbers; even tiny added noise can drop edit fields.
The unit test and `probe_workers.py` cover the failing seed 761685640, the
three/seven-child tree sizes, and exact binary scaling.
The optional **Randomize logarithms and powers** setting
(`cloakfox.opt.math_data_noise`, default false) restores noise to these five
functions at realm creation. Reload affected pages after changing it so their
workers use the same policy. Opting in can reproduce data loss and editor sync
failures; other math function noise remains active with this option off.
`probe_math_data_noise.py` tests default/off/on/master-off in real page and
worker realms, including native tree sizing, binary scaling and consistency.

`probe_identifier_leaks.py` remains the built-browser regression for numeric
bits, special values, errors/descriptors, frames/workers, container isolation and
live captured references. The actor unit test measures hot-path read counts;
it does not replace runtime checks or establish desktop frame-rate parity.

## Camera and microphone permission state

`probe_media_permissions.py` uses a disposable profile and local HTTP origin to
exercise the real native Permissions API with privacy enabled. It changes only
that test origin's permission manager entries, checks grants, revocations,
regrants, removal and Firefox's Always Ask semantics, and watches existing
PermissionStatus change events. Notification permission privacy and master-off
native behavior are also checked. It never calls getUserMedia/getDisplayMedia,
opens devices, or records audio/video, so it does not verify actual capture or
macOS TCC grants. Run with `CLOAKFOX_BIN` and optional `REPORT_DIR`.

### HackerRank media failover compatibility

`CloakfoxHackerRankMediaChild` is restricted to top-level HTTPS HackerRank
`/pair/` pages. Zoom failover changes the local participant ID, but this
application version retains its pre-failover ID. The actor refreshes that ID
from the connected SDK and advances the normal video render epoch. It never
starts camera/audio/sharing, changes permissions or transport, or alters
fingerprint signals. The site's old `isVideoDecodeReady` flag is left alone.
This is an application compatibility workaround, not a fix for the initial
Zoom transport failure. Site bundle changes may require adapter maintenance;
unsupported application shapes are left untouched. To opt out, set
`cloakfox.compat.hackerrank_media=false` and reload.

Run `node --test tests/fingerprint/test_hackerrank_media_recovery.mjs` for
repeat failovers, invalid/disconnected IDs, late initialization, client
replacement, teardown and opt-out. `probe_hackerrank_media_recovery.py` runs
that actor through Gecko's real cross-realm bindings in a disposable profile:

```sh
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python3 tests/fingerprint/probe_hackerrank_media_recovery.py
```

The probe first verifies the production origin restriction excludes its
loopback fixture, then registers the same actor for loopback in that disposable
profile only. It checks repeated failovers on two fresh loads, ID-dependent
video rendering, zero capture-start calls, unchanged readiness and opt-out.
It uses no real camera, screen or meeting. Live remote delivery requires an
actual peer and is separate from this application-state regression.

## Native virtual screen-management compatibility

`about:cloakfox` → **Screen API compatibility** groups the feature checkbox,
virtual screen count, and exact HTTPS origin list. The feature is off by default.
Choose a count from 1–8 (default 1); edit one origin per line and click **Save
origins**. Empty saves `[]`; **Reset origins** restores
`https://app.testdome.com`. Invalid drafts leave the saved list intact. Malformed
saved values display an error. Reload affected pages after changing these controls.

The native API requires all four gates: `cloakfox.enabled=true`,
`cloakfox.compat.screen_management=true`, the owning container's desktop
Chrome/Chromium/Edge identity, and its exact HTTPS principal origin in
`cloakfox.compat.screen_management.origins`. Firefox, mixed/malformed/mobile
identities, unlisted origins, HTTP and opaque frames have no added Window API.
Workers have no screen API and their `window-management` permission is denied.
A Chromium UA string selects these compatibility surfaces; it does not change
Gecko into the Chromium engine.

`getScreenDetails()` returns the same native `ScreenDetails` object and frozen
screen sequence for that inner window. Count is snapshotted when the inner
window is created: even changing it before the first API call needs a reload.
The primary display uses the owning container's Display persona (including its
available rectangle, depth, DPR and orientation). Additional displays repeat
that geometry horizontally with generic labels. Ordinary `screen` and window
DPR agree with the primary. Invalid topology/coordinate overflow falls back as
one coherent topology. Physical monitor changes do not alter this virtual list.

Fresh calls recheck the live gates and current document policy. The virtual
`window-management` permission is granted only to eligible, active, allowed
Windows; queried statuses are snapshots. Existing iframe/legacy policy denial
and exact modern `Permissions-Policy: window-management=()` are respected,
including inherited denial. Other modern allowlist syntax is not implemented.
Native Gecko applies a changed iframe `allow` attribute on its next navigation.
Camera, microphone, and actual screen capture retain Firefox permissions and
the standard sharing chooser.

```bash
export CLOAKFOX_BIN="/path/to/Cloakfox.app/Contents/MacOS/cloakfox"
python3 tests/fingerprint/probe_screen_management_settings.py
python3 tests/fingerprint/probe_screen_presentation.py
python3 tests/fingerprint/probe_screen_management.py
python3 tests/fingerprint/probe_testdome_recording.py
```

The first three probes use isolated local TLS fixtures and disposable profiles.
The recording probe is headful and uses canvas frames plus oscillator audio,
not camera/microphone/screen devices. It checks TestDome's observed public codec
order, jointly checks native `VideoEncoder` and `MediaRecorder` support, and
records the VP8/WebM fallback with Opus audio. Empty output and invalid EBML
headers fail; timeouts record progress, and sources/timers are cleaned up.
`--empty-output` deliberately exits unsuccessfully to verify that guard.
Set `REPORT_DIR` to retain JSON/native logs. These checks establish local APIs
and encoding, not physical capture, remote delivery or full assessment support.
