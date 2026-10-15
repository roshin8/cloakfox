/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* MediaQueryList is authoritative in native Gecko. The parser below remains
 * test-only legacy coverage; production does not patch page objects. */

// Desktop-plausible pins. color-gamut is OS-derived (macOS panels are wide-gamut).
// Pointer/hover are native: C++ handles persona touch counts and RDM overrides.
function pinsForOS(os) {
  return {
    "prefers-reduced-motion": "no-preference",
    "prefers-contrast": "no-preference",
    "forced-colors": "none",
    "inverted-colors": "none",
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

// Native nsMediaFeatures now resolves these features from the owning document.
// Do not replace MediaQueryList.matches: doing so makes JS disagree with CSS,
// change events, range/boolean syntax and explicit per-container preferences.
// Keep the actor registration inert for compatibility with existing builds.
export class CloakfoxMediaQueryChild extends JSWindowActorChild {
  handleEvent(_event) {}
}

// Test-only exports. ChromeUtils.importESModule consumers read the class and
// ignore these; they let the pure query-evaluation logic be unit-tested in Node
// (pass a nativeEval stub) without the chrome runtime.
export const _test = {
  pinsForOS, controlledMatch, hasControlledFeature, evalConjunction, evaluateMedia,
};
