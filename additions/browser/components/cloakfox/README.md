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

## What's NOT in this POC yet

- **C++ pref reader.** Today the Math actor reads prefs directly via
  `Services.prefs`. For C++ managers (canvas, WebGL, etc.) to consume
  the same prefs, we'd hook `nsGlobalWindowInner` construction to
  populate `RoverfoxStorageManager` from `cloakfox.container.<id>.*`.
  That's the next POC step — not needed for the Math actor itself.
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
