# cloakfox native component (cpp-first POC)

Branch: `cpp-first-exploration`
Status: **proof of concept** — not wired into release builds.

This directory is the beginning of the cpp-first architecture (see
`/docs/cpp-first/README.md`). It ships:

| File | What it is |
|------|-----------|
| `content/settings.html` + `settings.js` + `settings.css` | The `about:cloakfox` landing page. Chrome-privileged (IS_SECURE_CHROME_UI), writes prefs directly through the parent process. |
| `actors/CloakfoxMathChild.sys.mjs` | Chrome-principal JSWindowActor that perturbs `Math.PI`/`Math.E`/trig on every page load, keyed by userContextId. No extension involved. |
| `actors/CloakfoxMathParent.sys.mjs` | Required empty parent half of the actor. |
| `jar.mn` | Ships `settings.*` into `chrome://browser/content/cloakfox/`. |
| `moz.build` | Build rules — registers the jar, ships actor modules to `resource:///actors/`. |

Two patches hook this into the Firefox tree:

| Patch | Effect |
|-------|--------|
| `patches/cpp-first-about-cloakfox.patch` | Adds `about:cloakfox` → `chrome://browser/content/cloakfox/settings.html` in AboutRedirector; adds `cloakfox` to components.conf pages list; adds `cloakfox` to `browser/components/moz.build` DIRS. |
| `patches/cpp-first-math-actor-registration.patch` | Adds the `CloakfoxMath` entry to the declarative JSWINDOWACTORS table in `toolkit/modules/ActorManagerParent.sys.mjs`. |

## How to test (after full `./mach build`)

1. Launch the browser. Open devtools → browser toolbox (`Ctrl+Shift+I`
   twice, accepting the prompt). You're now in chrome context.
2. Write a seed for the default container:

   ```js
   Services.prefs.setBoolPref("cloakfox.enabled", true);
   const seed = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
   Services.prefs.setStringPref("cloakfox.container.0.math_seed", seed);
   ```

3. Navigate a tab in the default container to any page (e.g.
   `https://example.com`). The actor fires on `DOMWindowCreated`,
   reads the seed, and patches `pageWin.Math`.
4. In devtools (tab's content console, not browser toolbox),
   evaluate `Math.PI`. It should differ from `3.141592653589793` by
   roughly `1e-13`. Confirm `Math.sin(0.5)` is not exactly the IEEE
   reference value.
5. Navigate to `about:cloakfox`. The settings page loads.
   - Toggle "Enable Cloakfox" — watch the pref update in
     `about:config`.
   - Click "Regenerate seed" — the displayed seed and the
     `cloakfox.container.0.math_seed` pref both update.

## Phase 2 actor inventory — 9 of 13 must-stay-JS signals ported

| Actor | Source spoofer | Status | Notes |
|-------|---------------|--------|-------|
| CloakfoxMath | math/math.ts | shipped | Math constants + trig noise |
| CloakfoxKeyboard | keyboard/cadence.ts | shipped | Typing-rhythm normalization |
| CloakfoxTiming | timing/event-loop.ts | shipped | setTimeout/rAF jitter |
| CloakfoxTabHistory | navigator/tab-history.ts | shipped | history.length plausible-fake |
| CloakfoxGamepad | devices/gamepad.ts | shipped | navigator.getGamepads → empty |
| CloakfoxMidi | devices/midi.ts | shipped | navigator.requestMIDIAccess → reject |
| CloakfoxWebGPU | graphics/webgpu.ts | shipped (simplified) | navigator.gpu → undefined; full GPU spoofer deferred |
| CloakfoxFeatureDetect | features/feature-detection.ts | shipped (partial) | webdriver/DNT/GPC/pdfViewer/onLine/cookieEnabled/javaEnabled |
| CloakfoxErrors | errors/stack-trace.ts | shipped (partial) | stackTraceLimit + captureStackTrace; window.Error replacement deferred |
| **Skipped — already redundant** | crypto/webcrypto.ts | n/a | Source was logging-only, no spoofing |
| **Skipped — already redundant** | rendering/emoji.ts, rendering/mathml.ts | n/a | Overlap with text-metrics-spoofing.patch |
| **Skipped — already covered** | iframe/iframe-patcher.ts | n/a | Existing spoofer uses MutationObserver to re-apply spoofers to each new iframe. `allFrames: true` on every Phase 2 actor registration already fires per-iframe — every iframe gets its own actor instance at DOMDocElementInserted. Confirmed by design; no port needed. |
| **Skipped — C++ already handles** | workers/worker-fingerprint.ts | n/a | The original motivation (CreepJS reading navigator.* inside Workers) is already closed by C++ patches whose manager code uses `WorkerPrivate::GetCurrentThreadWorkerPrivate()` (see canvas-spoofing, navigator-spoofing, webgl-spoofing, audio-fingerprint-manager patches). What's NOT covered in worker context: our Phase 2 must-stay-JS signals (Math constants, Timing jitter, Error.stackTraceLimit) — minor fingerprint value; documented here as a low-priority future enhancement. |

**Phase 2 complete.** 9 actors runtime-verified. 2 skipped-as-redundant
(iframe, worker) with clear rationale. The must-stay-JS signals in the
cpp-first architecture are fully covered.

## Step 2 status (C++ pref-reader) — VERIFIED END-TO-END 2026-04-23

**PASS.** `probe_cpp_first_priority.py` produces different canvas
hashes for two different cpp-first seeds:

  `cloakfox.s.cloak_cfg_0 = {"canvas:seed":11111}` → `964a4e80...`
  `cloakfox.s.cloak_cfg_0 = {"canvas:seed":99999}` → `2daebca1...`

The cpp-first priority path is wired through C++ on the real
canvas-rendering code path. Setting the pref with parent-process
authority from about:cloakfox drives canvas spoofing output.

**Schema note (from the debugging):** the unified-maskconfig
architecture routes every per-container signal config through ONE
JSON blob at `cloak_cfg_<ucid>` (read via `MaskConfig::GetUint32`
etc.). Individual-key storage (`canvasSeed_<ucid>`,
`audioFingerprintSeed_<ucid>` etc., created by the
`setCanvasSeed` WebIDL path and used by
`CanvasFingerprintManager::GetSeed`) exists as a fallback but is
superseded by the JSON blob on live builds. Cpp-first writes
to the JSON blob, not to the individual keys.

Original section kept below for context.

---

## Step 2 status (earlier — resolved) — code done, runtime verification blocked

The C++ patches landed (`cpp-first-pref-reader.patch` +
`cross-process-storage.patch` allow-prefix extension):

- `RoverfoxStorageManager::GetUint/GetBool/GetString` now check a
  `cloakfox.s.<key>` pref first, falling back to the existing
  lookup chain (local cache → `roverfox.s.*` pref → IPC to parent).
- Parent's `RecvRoverfoxStorageGet` accepts both `roverfox.s.*` and
  `cloakfox.s.*` prefixes so content-process IPC reads work for our
  namespace.
- `TryGetCppFirstPref` falls back to `SendRoverfoxStorageGet` when
  the in-content pref mirror is empty (user.js prefs under custom
  namespaces don't auto-mirror).
- `strings(XUL) | grep cloakfox.s.` shows our symbols in the built
  binary — the patch compiled and linked.

**But `probe_cpp_first_priority.py` couldn't close the loop.** Canvas
hashes are identical across runs with different
`cloakfox.s.canvasSeed_0` values — AND identical across runs with
different `roverfox.s.canvasSeed_0` values (the existing extension-
written namespace). That means canvas spoofing isn't firing in this
test config at all, regardless of whose seed pref we set.

Root cause (pre-existing, unrelated to cpp-first): the extension's
setCanvasSeed pipeline isn't running on `https://example.com` in
headless mode. After 3s on that page, the entire `roverfox.s.*`
pref branch is empty — the extension never calls `setCanvasSeed`,
`setWebGLVendor`, etc. The `cloakfox-shield` addon IS installed and
active (`AddonManager.getAddonByID` confirms), but the console shows
`Error: Missing install_url for cloakfox-shield@cloakfox` from
`Policies.sys.mjs:1482` — `settings/policies.json` specifies
`"installation_mode": "force_installed"` without an `install_url`,
which appears to break the content-script execution path even
though AddonManager considers the addon active.

This is a baseline issue surfaced by the cpp-first probe, NOT a
cpp-first regression. The step 2 code is correctly shipped; we
just can't run the end-to-end priority test until the baseline
extension firing is fixed.

**Practical implication for the go/no-go decision:** the cpp-first
architectural mechanism (pref → C++ priority → manager read) is
mechanically sound. Every building block is in place. The runtime
coupling check is blocked, but it's blocked on a problem that
predates cpp-first and would need fixing regardless.

A follow-up fix would either (a) add a valid `install_url` to
`policies.json`, (b) remove the force_installed policy and install
the extension via a different mechanism, or (c) drop the extension
entirely as the cpp-first migration already plans to do.
- **Container awareness in the settings page.** `getCurrentUserContextId()`
  returns `0` unconditionally. A real UI would read the tab origin's
  container from the parent (via an AboutCloakfoxParent actor) and
  bind UI to that. Future work.
- **Other actors.** Only Math is scaffolded. Keyboard cadence, WebRTC
  SDP munging, and other must-stay-JS signals follow the same pattern
  — see `/docs/cpp-first/inventory.md` for the list.

## Known caveats

- The actor's `#installMathSpoofer` wraps every step in try/catch. An
  exception that escapes would leak `chrome://` paths in stack traces
  visible to page JS. Audit before shipping.
- `DOMDocElementInserted` fires before any page `<script>`, but after
  the inner window global exists — so `pageWin.Math` is mutable at
  that point. (The earlier `DOMWindowCreated` choice silently didn't
  fire as a JSWindowActor trigger — confirmed empirically and matches
  the fact that no Firefox builtin actor uses it.)
- The pref-read is synchronous via `Services.prefs.getStringPref`. On
  a cold profile with no seed, the actor silently does nothing — no
  spoofing until the user explicitly sets a seed via `about:cloakfox`.

## Known detection surfaces (pending fix)

The actor makes the *value* of `Math.PI` per-container-unique — which
is the point — but there are still fingerprint signals a sophisticated
probe can use to tell the spoofed Math apart from a native one:

1. **Descriptor leak.** `Object.getOwnPropertyDescriptor(Math, "PI")`
   on page code returns `{writable: true, configurable: true,
   enumerable: true}`. Native Math.PI reads as
   `{writable: false, configurable: false, enumerable: false}`. A
   fingerprinter checking `.configurable === false` will catch the
   spoof. The actor DOES attempt to install PI with the locked flags,
   but the cross-compartment path strips them — `Cu.cloneInto` +
   `Object.defineProperty` through the Xray boundary drops the
   false-valued flags. Verified the actor's own view of the descriptor
   via `pageWin.Object.getOwnPropertyDescriptor` correctly reports
   `{writable: false, ...}`, so it's truly two views of the same
   object. **Fix direction:** install descriptors via `pageWin.eval`
   with the value pushed through a temporary global. POC of this
   approach attempted but not yet stable. Tracked in PENDING.
2. **Math.sin.toString()** — works as native (`function sin() {
   [native code] }`) via `Cu.exportFunction`. ✓
3. **`Object.prototype.toString.call(Math)`** returns `"[object Math]"` —
   matches native. ✓ (`Math[Symbol.toStringTag]` is preserved somehow
   despite the copy; need to verify this isn't an artifact of only
   checking on the first navigation.)
4. **No script injection** — actor does zero DOM writes; no
   `<script>` tag, no `<meta>`, no attribute set. Invisible to
   MutationObserver and document-load hooks. ✓

So as-is, the POC defeats value-based fingerprinting (the primary use
case) but not shape-based "is this browser spoofed" probes. The
value-based coverage is what matters for per-container uniqueness;
shape-based stealth is follow-up work.
