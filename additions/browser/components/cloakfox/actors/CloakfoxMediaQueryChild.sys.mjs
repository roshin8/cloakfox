/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: pin fingerprinting-relevant CSS media features so window.matchMedia
 * reports persona-coherent, host-independent values instead of leaking the real
 * device/OS (prefers-color-scheme, pointer/hover, forced-colors, color-gamut …).
 *
 * Implemented by overriding the INHERITED MediaQueryList.prototype.matches
 * getter (native flags, native identity) — no own-property tell.
 *
 * Correctness model — the query result is computed, not first-clause-guessed
 * and not all-or-nothing deferred:
 *   - Each CONTROLLED atomic condition (a feature we pin) uses our pinned truth.
 *   - Each UNCONTROLLED atomic condition (min-width, orientation, resolution,
 *     ranges, nested groups…) is evaluated NATIVELY via `nativeEval` — a fresh
 *     native MediaQueryList read — so its real value is honored.
 *   - Those are combined under the real boolean structure (and / comma-OR / not
 *     / media type). We only override when the query actually references a
 *     controlled feature; otherwise we defer to native.
 *
 * This is what keeps the answer consistent with reality and free of the
 * "impossible result" oracle in BOTH directions, e.g. on a persona pinned to
 * prefers-color-scheme:light while the host is dark:
 *   "(prefers-color-scheme: dark)"                       -> false  (pinned)
 *   "(prefers-color-scheme: dark) and (min-width: 100px)"-> false  (pin ∧ native)
 *   "(prefers-color-scheme: light) and (min-width: 9e9px)"-> false (pin ∧ native)
 * A naive "defer the whole query when any clause is uncontrolled" would return
 * the host's real dark value for the middle case — a tell. Note: this covers
 * the JS matchMedia API only, not CSS @media in stylesheets (that needs C++).
 */

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

// Evaluate a SINGLE parenthesized condition "(feature: value)" against the pins.
// Returns the spoofed boolean for a controlled feature, or undefined for
// "not a controlled simple feature:value" (uncontrolled feature, range,
// bare-boolean feature, nested group) — those are handled natively by the caller.
function controlledMatch(group, pins) {
  const m = /^\(\s*([a-z-]+)\s*:\s*([a-z0-9.-]+)\s*\)$/.exec(group);
  if (!m) return undefined;
  const feature = m[1];
  const value = m[2];
  if (!(feature in pins)) return undefined;
  const pinned = pins[feature];
  if (feature === "color-gamut") {
    // matches if the display's gamut is at least the queried one.
    return GAMUT_RANK[value] !== undefined &&
           GAMUT_RANK[pinned] >= GAMUT_RANK[value];
  }
  return value === pinned;
}

// Does the media string reference ANY controlled feature? If not, there is
// nothing to spoof and we defer to native without any native re-evaluation.
function hasControlledFeature(media, pins) {
  const re = /\(\s*([a-z-]+)\s*:/g;
  let m;
  while ((m = re.exec(media)) !== null) {
    if (m[1] in pins) return true;
  }
  return false;
}

// Evaluate one conjunctive query (the piece between commas): optional leading
// not/only, an optional media type, and "and"-joined conditions. Controlled
// conditions use the pins; uncontrolled ones are evaluated via nativeEval.
// Returns { value, sawControlled } or undefined to defer the whole string.
function evalConjunction(query, pins, nativeEval) {
  const s = query.trim().toLowerCase();
  if (!s) return undefined;
  // `or`-combined conditions (MQ4) are rare and not parsed here — defer rather
  // than risk a wrong result.
  if (/\bor\b/.test(s)) return undefined;
  let negate = false;
  let value = true;
  let sawControlled = false;
  const parts = s.split(/\s+and\s+/);
  for (let i = 0; i < parts.length; i++) {
    let p = parts[i].trim();
    if (i === 0) {
      if (p.startsWith("not ")) { negate = true; p = p.slice(4).trim(); }
      else if (p.startsWith("only ")) { p = p.slice(5).trim(); }
    }
    if (p === "") return undefined;
    if (p.startsWith("(")) {
      const controlled = controlledMatch(p, pins);
      if (controlled !== undefined) {
        sawControlled = true;
        value = value && controlled;
      } else {
        // Uncontrolled or non-simple condition: honor its real value.
        if (!nativeEval) return undefined;
        value = value && !!nativeEval(p);
      }
    } else if (p === "screen" || p === "all") {
      // matches a normal screen browsing context; no effect on value.
    } else if (p === "print" || p === "speech") {
      value = false;
    } else {
      return undefined; // unknown media type / token → defer
    }
  }
  return { value: negate ? !value : value, sawControlled };
}

// Evaluate a full media-query string (comma-separated query LIST, OR-joined).
// Returns a boolean when the string references a controlled feature and every
// query is parseable; otherwise undefined so the caller defers to native.
function evaluateMedia(media, pins, nativeEval) {
  if (!media || typeof media !== "string") return undefined;
  if (!hasControlledFeature(media, pins)) return undefined; // nothing to spoof
  let sawControlled = false;
  let anyTrue = false;
  for (const q of media.split(",")) {
    const r = evalConjunction(q, pins, nativeEval);
    if (r === undefined) return undefined; // unparseable query → defer all
    sawControlled = sawControlled || r.sawControlled;
    anyTrue = anyTrue || r.value;
  }
  return sawControlled ? anyTrue : undefined;
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
    // Capture the NATIVE matchMedia now, before any page script runs, so our
    // native evaluation of uncontrolled conditions can't be observed or spoofed
    // by a page that later redefines window.matchMedia.
    const origMatchMedia =
      typeof pageWin.matchMedia === "function" ? pageWin.matchMedia : null;

    const pins = pinsForOS(osFromPlatform(win.navigator.platform || ""));

    const newGetter = Cu.exportFunction(function () {
      try {
        // Evaluate an uncontrolled atomic condition natively, bypassing our
        // patched prototype getter (no recursion, no page-override exposure).
        const nativeEval = origMatchMedia
          ? (atom) => {
              try { return !!origGetter.call(origMatchMedia.call(pageWin, atom)); }
              catch (_e) { return false; }
            }
          : null;
        const spoof = evaluateMedia(this.media, pins, nativeEval);
        if (spoof !== undefined) return spoof;
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

// Test-only exports. ChromeUtils.importESModule consumers read the class and
// ignore these; they let the pure query-evaluation logic be unit-tested in Node
// (pass a nativeEval stub) without the chrome runtime.
export const _test = {
  pinsForOS, controlledMatch, hasControlledFeature, evalConjunction, evaluateMedia,
};
