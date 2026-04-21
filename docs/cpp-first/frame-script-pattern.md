# Privileged frame-script pattern for non-C++ spoofers

**Branch:** `cpp-first-exploration`
**Status:** design; prototype in `patches/cpp-first-math-actor.patch`
(pending).
**Date:** 2026-04-21

## Why this exists

Some fingerprint signals have no clean C++ hook — see inventory.md. In
the cpp-first architecture we need a way to inject spoofer JS into
every content window that:

- Runs with **chrome principal**, not extension principal and not
  page principal.
- Needs **no webextension manifest**, content_scripts, or Func-gated
  WebIDL.
- Is **invisible to page inspection** because it runs in a different
  compartment — the page can't enumerate chrome-principal globals,
  and `exportFunction`'d getters stringify as `[native code]` with no
  extension-file references anywhere.
- Loads at **document_start** on every navigation, before any page
  script runs — no race.

Firefox's `JSWindowActor` framework gives us exactly this.

## JSWindowActor vs. legacy frame scripts

Firefox deprecated the old `messageManager`-based frame scripts in
favor of JSWindowActor pairs (parent + child). For Cloakfox's
purposes we only need the **child** half — it runs in the content
process for every top-level or frame window, has chrome principal,
and can manipulate the page via `wrappedJSObject` just like a
content script's ISOLATED world does today.

## Registration

Add to `browser/actors/BrowserGlue.sys.mjs` (or a Cloakfox-specific
actor-registry module loaded at startup):

```js
ChromeUtils.registerWindowActor("CloakfoxMath", {
  child: {
    esModuleURI: "chrome://cloakfox/content/actors/MathChild.sys.mjs",
    events: {
      DOMWindowCreated: { mozSystemGroup: true },
    },
  },
  allFrames: true,
  matches: ["*://*/*"],
});
```

- `DOMWindowCreated` fires in content process before any page script
  runs. That's our injection point.
- `allFrames: true` covers iframes.
- `matches: ["*://*/*"]` skips about: / chrome: URIs we don't want to
  spoof.
- No `includeChrome: true` — we never want this running in the
  browser UI itself.

## Child actor body

```js
export class CloakfoxMathChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMWindowCreated") return;
    this.installMathSpoofer();
  }

  installMathSpoofer() {
    const win = this.contentWindow;
    if (!win) return;
    const pageWin = win.wrappedJSObject;

    // Read per-container seed from prefs (via Services, runs in
    // content process but Services.prefs is accessible as a
    // read-only mirror here).
    const seed = this.getMathSeedForWindow(win);
    if (!seed) return;

    // Generate the per-container perturbation.
    const prng = this.buildPRNG(seed);
    const piOffset = (prng.next() - 0.5) * 1e-13;
    const eOffset  = (prng.next() - 0.5) * 1e-13;

    // Math is a namespace object. PI / E are non-writable non-
    // configurable per spec, so we replace Math itself with a
    // proxy-free plain object whose properties are our spoofed
    // values. exportFunction isn't needed here — we create the
    // object in the chrome compartment and cloneInto it.
    const spoofedMath = Cu.cloneInto({
      ...pageWin.Math,  // copy all methods first
    }, pageWin);

    // Override the constants post-copy to avoid the "copy preserves
    // non-configurable descriptor" pitfall we hit in MAIN-world
    // spoofer earlier.
    Object.defineProperty(spoofedMath, "PI", {
      value: pageWin.Math.PI + piOffset,
      writable: false,
      configurable: false,
    });
    Object.defineProperty(spoofedMath, "E", {
      value: pageWin.Math.E + eOffset,
      writable: false,
      configurable: false,
    });

    // Method wrap for trig / log / exp — chrome-compartment
    // function, exportFunction into page.
    const origSin = pageWin.Math.sin;
    const noisySin = exportFunction(
      function (x) {
        const r = origSin.call(this, x);
        return Number.isFinite(r) && !Number.isInteger(r)
          ? r + (prng.next() - 0.5) * 1e-12
          : r;
      },
      pageWin,
      { defineAs: "sin" },
    );
    spoofedMath.sin = noisySin;
    // ... repeat for cos, tan, exp, log, etc.

    // Swap Math on the page's window. Math is NOT on the Window
    // prototype — it's an own property of the global. Need to use
    // wrappedJSObject.Math = spoofedMath, which works across
    // compartments thanks to Xray vision being bidirectional here.
    pageWin.Math = spoofedMath;
  }

  getMathSeedForWindow(win) {
    const bc = win.docShell?.browsingContext;
    if (!bc) return null;
    const userContextId = bc.originAttributes.userContextId ?? 0;
    // Cloakfox seed lives in prefs as cloakfox.container.<id>.math_seed
    const prefName = `cloakfox.container.${userContextId}.math_seed`;
    return Services.prefs.getCharPref(prefName, "") || null;
  }

  buildPRNG(seed) {
    // xorshift128+ derived from seed, same algorithm as lib/crypto.ts.
    // Inline so we don't need a shared module.
    // ... (see prototype patch)
  }
}
```

## What this achieves vs. today's inject/spoofers/math/math.ts

| Property | Today (MAIN script) | cpp-first (actor) |
|---|---|---|
| Principal | Page | Chrome (system) |
| Script origin | moz-extension://.../math.ts | chrome://cloakfox/content/actors/MathChild.sys.mjs |
| Stack-trace leak | `moz-extension://` in frames | `chrome://` (paranoid) or hidden (real Firefox chrome) |
| Visibility via `defineProperty` descriptor | Getter with page function | Either no getter at all (value replacement) or `[native code]` via `defineAs` |
| Runs before page scripts? | Yes (document_start MAIN) | Yes (DOMWindowCreated, earlier than document_start) |
| Requires Function.prototype.toString patch? | Yes | No — exported functions stringify as native |
| Requires `[Func=...]` gate? | N/A (page world) | N/A (not exposed as WebIDL at all) |
| Requires documentElement bridge? | Yes (for skip gating) | No — C++ already owns its signals; actor owns its own |

## What it does NOT achieve

- It's still JS. Running in chrome compartment hides most detection
  surface but e.g. any exception escaping the actor shows
  `chrome://cloakfox/...` in the stack. Catch all exceptions
  religiously.
- `DOMWindowCreated` timing is slightly different from `document_start`
  — in particular, the DOM isn't built yet. Can't query the `<html>`
  element. For Math that's irrelevant, but for spoofers that need to
  read something from the page, use `DOMContentLoaded` instead.
- Some signals (e.g. `performance.now` jitter) need a per-origin
  offset that's stable across reloads. That's pref-driven seed
  material same as canvas.

## Actor registration site

Firefox registers its own actors via
`browser/actors/BrowserGlue.sys.mjs` or modular registry files. We
add Cloakfox actors as a patch to a new file
`browser/actors/CloakfoxActors.sys.mjs` that `BrowserGlue` imports.

One patch, additive, doesn't touch existing actor definitions.

## Inventory mapping

For each signal in inventory.md marked "must stay JS," we add one
actor (or one more method to a shared Cloakfox actor). First ones to
prototype:

1. **CloakfoxMath** — Math.PI, Math.E, Math.sin/cos/tan/log/exp/etc.
2. **CloakfoxWebRTC** — RTCPeerConnection createOffer SDP rewrite.
3. **CloakfoxKeyboard** — KeyboardEvent dispatch jitter.
4. **CloakfoxGraphics** — DOMRect / text-metrics / SVG-bbox jitter
   (these could conceivably move to C++ but it's a large effort).

One actor per signal family, not one monolithic actor, so bisecting
regressions and toggling per-feature stays easy.

## Prototype scope

`patches/cpp-first-math-actor.patch` will add:

1. `browser/actors/CloakfoxMathChild.sys.mjs` — the actor body above.
2. `browser/actors/CloakfoxMathParent.sys.mjs` — minimal parent half
   (required by JSWindowActor registration even if empty).
3. Chrome manifest entry to serve them.
4. Registration call in a new `browser/actors/CloakfoxActors.sys.mjs`
   imported from `BrowserGlue.sys.mjs`.
5. No changes to existing files beyond the BrowserGlue import line.

~150 lines total including comments.
