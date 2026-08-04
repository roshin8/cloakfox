/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: pin fingerprinting-relevant CSS media features so window.matchMedia
 * reports persona-coherent, host-independent values instead of leaking the real
 * device/OS (prefers-color-scheme, pointer/hover, forced-colors, color-gamut …).
 *
 * Implemented by overriding the INHERITED MediaQueryList.prototype.matches
 * getter (native flags, native identity) — no own-property tell — and reading
 * `this.media` to decide per query. Uncontrolled features delegate to the real
 * getter, so layout-affecting queries (min-width, orientation, resolution) are
 * untouched. Note: this covers the JS matchMedia API only, not CSS @media
 * evaluated in stylesheets (that needs a C++ path).
 */

// Read the container's persona so the JS pins agree with the values the C++
// stylesheet path uses (document:prefersColorScheme, mediaFeature:colorGamut,
// mediaFeature:prefersContrast). Without this the two paths can disagree — a
// CSS `@media (prefers-color-scheme: dark)` rule applying while matchMedia
// reports light is impossible in a real browser and exposes the spoof.
function personaMediaKeys(win) {
  try {
    const ucid =
      win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const raw = Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${ucid}`, "");
    return raw ? JSON.parse(raw) : {};
  } catch (_e) {
    return {};
  }
}

const GAMUT_BY_INDEX = ["srgb", "p3", "rec2020"];
const CONTRAST_BY_INDEX = ["no-preference", "less", "more", "custom"];

// Desktop-plausible pins. color-gamut is OS-derived (macOS panels are wide-gamut).
function pinsForOS(os) {
  return {
    "prefers-color-scheme": "light",
    "prefers-reduced-motion": "no-preference",
    "prefers-contrast": "no-preference",
    "forced-colors": "none",
    "inverted-colors": "none",
    "pointer": "fine",
    "any-pointer": "fine",
    "hover": "hover",
    "any-hover": "hover",
    "color-gamut": os === "macos" ? "p3" : "srgb",
    "dynamic-range": "standard",
    "update": "fast",
  };
}

// color-gamut is a "min" feature: a p3 display matches srgb AND p3.
const GAMUT_RANK = { srgb: 0, p3: 1, rec2020: 2 };

// Evaluate ONE `(feature: value)` term against the pins, or undefined if the
// feature isn't one we control.
function controlledTerm(feature, value, pins) {
  feature = feature.toLowerCase();
  value = value.toLowerCase();
  if (!(feature in pins)) return undefined;
  const pinned = pins[feature];
  if (feature === "color-gamut") {
    // "min" semantics: a p3 display matches both srgb and p3.
    return GAMUT_RANK[value] !== undefined &&
           GAMUT_RANK[pinned] >= GAMUT_RANK[value];
  }
  return value === pinned;
}

const FEATURE_RE = /\(\s*([a-z-]+)\s*:\s*([a-z0-9.-]+)\s*\)/gi;
// Always-true / always-false stand-ins, viewport-independent.
const ALWAYS_TRUE = "(min-width: 0px)";
const ALWAYS_FALSE = "(min-width: 99999999px)";

// Rewrite a media string, replacing controlled feature terms with constant
// stand-ins and leaving everything else intact. Returns null when the query
// contains no controlled feature (caller should just use the native getter).
//
// Rewriting rather than short-circuiting is what makes compound queries
// correct: `and`, `,` (or) and `not` are then evaluated NATIVELY over the
// substituted string, so `(pointer: fine) and (min-width: 99999px)` is false
// and `not all and (pointer: fine)` is false — matching a real browser. The
// earlier first-match-wins approach returned true for both, an impossible
// result that advertised the spoofing layer.
function rewriteMedia(media, pins) {
  let touched = false;
  const out = media.replace(FEATURE_RE, (whole, feature, value) => {
    const res = controlledTerm(feature, value, pins);
    if (res === undefined) return whole;
    touched = true;
    return res ? ALWAYS_TRUE : ALWAYS_FALSE;
  });
  return touched ? out : null;
}

function osFromPlatform(platform) {
  if (/win/i.test(platform)) return "windows";
  if (/mac/i.test(platform)) return "macos";
  return "linux";
}

// Native accessor reports name "get matches" length 0; match it (Xray-waived).
function setGetterIdentity(getterFn) {
  const waived = Cu.waiveXrays(getterFn);
  try {
    Object.defineProperty(waived, "name", {
      value: "get matches", writable: false, enumerable: false, configurable: true,
    });
    Object.defineProperty(waived, "length", {
      value: 0, writable: false, enumerable: false, configurable: true,
    });
  } catch (_e) { /* best effort */ }
  return getterFn;
}

export class CloakfoxMediaQueryChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;
    const proto = pageWin.MediaQueryList?.prototype;
    if (!proto) return;
    const desc = Object.getOwnPropertyDescriptor(proto, "matches");
    const origGetter = desc?.get;
    if (!origGetter) return;

    const pins = pinsForOS(osFromPlatform(win.navigator.platform || ""));

    // Persona-emitted values win, so JS matchMedia and the C++ stylesheet path
    // report the same thing. Fall back to the OS-derived defaults above when a
    // key is absent (older personas / no cloak_cfg yet).
    const persona = personaMediaKeys(win);
    const cs = persona["document:prefersColorScheme"];
    if (cs === 0 || cs === 1) {
      pins["prefers-color-scheme"] = cs ? "dark" : "light";
    }
    const gamut = persona["mediaFeature:colorGamut"];
    if (GAMUT_BY_INDEX[gamut] !== undefined) {
      pins["color-gamut"] = GAMUT_BY_INDEX[gamut];
    }
    const contrast = persona["mediaFeature:prefersContrast"];
    if (CONTRAST_BY_INDEX[contrast] !== undefined) {
      pins["prefers-contrast"] = CONTRAST_BY_INDEX[contrast];
    }

    const newGetter = Cu.exportFunction(function () {
      try {
        const rewritten = rewriteMedia(this.media, pins);
        if (rewritten !== null) {
          // Evaluate the substituted query with the NATIVE getter so the
          // media-query grammar (and / , / not / only) is handled by Gecko.
          return origGetter.call(pageWin.matchMedia(rewritten));
        }
      } catch (_e) { /* fall through to native */ }
      return origGetter.call(this);
    }, pageWin);
    setGetterIdentity(newGetter);

    try {
      // Native MediaQueryList.prototype.matches is {enumerable:true, configurable:true}.
      Object.defineProperty(proto, "matches", {
        get: newGetter, enumerable: true, configurable: true,
      });
    } catch (_e) { /* non-configurable on some builds — best effort */ }
  }
}
