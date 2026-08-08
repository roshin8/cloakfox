/* Unit test for CloakfoxMediaQueryChild's query evaluation (finding #6).
 * Runs in plain Node — stubs the chrome globals the module references at
 * class-eval time, then imports the real module and drives its _test exports.
 *
 *   node --test tests/fingerprint/test_mediaquery_logic.mjs
 *
 * `nativeEval` models the REAL environment for uncontrolled conditions. The
 * critical cases prove the fix closes the fingerprint oracle in BOTH directions
 * (a satisfiable uncontrolled term must not leak the real controlled value).
 */
import test from "node:test";
import assert from "node:assert/strict";

globalThis.JSWindowActorChild = class {};

const mod = await import(
  "../../additions/browser/components/cloakfox/actors/CloakfoxMediaQueryChild.sys.mjs"
);
const { pinsForOS, evaluateMedia } = mod._test;

const mac = pinsForOS("macos"); // prefers-color-scheme: light, color-gamut: p3
const linux = pinsForOS("linux"); // color-gamut: srgb

// Model a real host that is in DARK mode with a normal desktop viewport, so a
// leak of the real prefers-color-scheme (dark) through an uncontrolled clause
// would be observable. Only UNCONTROLLED atoms ever reach nativeEval.
function nativeEval(atom) {
  const a = atom.toLowerCase();
  if (/\(\s*min-width:\s*(\d+)px\s*\)/.test(a)) {
    const px = Number(RegExp.$1);
    return px <= 1280; // viewport is 1280px wide
  }
  if (/\(\s*max-width:\s*(\d+)px\s*\)/.test(a)) {
    return Number(RegExp.$1) >= 1280;
  }
  if (a.includes("orientation: landscape")) return true;
  if (a.includes("orientation: portrait")) return false;
  if (a.includes("min-resolution")) return true;
  // A controlled atom should NEVER reach nativeEval; if it does, surface the
  // host's real (dark) value so a leak would fail the assertions below.
  if (a.includes("prefers-color-scheme: dark")) return true;   // host is dark
  if (a.includes("prefers-color-scheme: light")) return false;
  return false;
}
const ev = (q, pins = mac) => evaluateMedia(q, pins, nativeEval);

test("standalone controlled feature is spoofed to the pin", () => {
  assert.equal(ev("(prefers-color-scheme: light)"), true);
  assert.equal(ev("(prefers-color-scheme: dark)"), false); // pinned light, host dark
});

test("ORACLE (unsatisfiable term): pin ∧ native-false = false", () => {
  assert.equal(ev("(prefers-color-scheme: light) and (min-width: 99999px)"), false);
  assert.equal(ev("(min-width: 99999px) and (prefers-color-scheme: light)"), false);
});

test("ORACLE (satisfiable term): must NOT leak the real controlled value", () => {
  // Host is really dark. Standalone dark returns pinned false. A dark query
  // AND'd with a TRUE uncontrolled term must STILL be false — never the host's
  // real dark (which a naive whole-query deferral would leak as true).
  assert.equal(ev("(prefers-color-scheme: dark) and (min-width: 100px)"), false);
  assert.equal(ev("(prefers-color-scheme: dark) and (orientation: landscape)"), false);
  // Comma-OR variant with a true uncontrolled term is genuinely true in reality
  // (the width matches), and a light browser returns true here too — consistent.
  assert.equal(ev("(prefers-color-scheme: dark), (min-width: 100px)"), true);
  // Light pin AND a true uncontrolled term = true (matches a real light browser).
  assert.equal(ev("(prefers-color-scheme: light) and (min-width: 100px)"), true);
});

test("uncontrolled clauses honor their real native value", () => {
  assert.equal(ev("(prefers-color-scheme: light) and (min-width: 100px)"), true);
  assert.equal(ev("(prefers-color-scheme: light) and (max-width: 100px)"), false);
  assert.equal(ev("(pointer: fine) and (orientation: portrait)"), false);
  assert.equal(ev("(pointer: fine) and (orientation: landscape)"), true);
});

test("pure uncontrolled queries defer (undefined)", () => {
  assert.equal(ev("(min-width: 500px)"), undefined);
  assert.equal(ev("(orientation: portrait)"), undefined);
  assert.equal(ev("screen"), undefined);
  assert.equal(ev("(400px <= width <= 700px)"), undefined);
});

test("all-controlled conjunction ANDs correctly", () => {
  assert.equal(ev("(pointer: fine) and (hover: hover)"), true);
  assert.equal(ev("(pointer: coarse) and (hover: hover)"), false);
});

test("comma list is OR across queries", () => {
  assert.equal(ev("(prefers-color-scheme: dark), (prefers-color-scheme: light)"), true);
  assert.equal(ev("(prefers-color-scheme: dark), (prefers-reduced-motion: reduce)"), false);
});

test("not inverts a controlled query", () => {
  assert.equal(ev("not (prefers-color-scheme: dark)"), true);
  assert.equal(ev("not (prefers-color-scheme: light)"), false);
});

test("media type prefix is honored", () => {
  assert.equal(ev("screen and (prefers-color-scheme: light)"), true);
  assert.equal(ev("print and (prefers-color-scheme: light)"), false);
});

test("color-gamut is a min-feature (p3 matches srgb and p3)", () => {
  assert.equal(ev("(color-gamut: srgb)"), true);
  assert.equal(ev("(color-gamut: p3)"), true);
  assert.equal(ev("(color-gamut: rec2020)"), false);
  assert.equal(ev("(color-gamut: p3)", linux), false); // srgb < p3
});

test("bare boolean-context feature has no controlled feature → defer", () => {
  assert.equal(ev("(pointer)"), undefined);
  assert.equal(ev("(color)"), undefined);
});

test("or-combined queries defer (not parsed)", () => {
  assert.equal(ev("(prefers-color-scheme: dark) or (pointer: fine)"), undefined);
});

test("without nativeEval, a mixed query defers rather than guess", () => {
  assert.equal(
    evaluateMedia("(prefers-color-scheme: dark) and (min-width: 100px)", mac, null),
    undefined
  );
});
