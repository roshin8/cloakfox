/* Guard test for the cross-engine HTTP/3 chimera.
 *
 *   node --test tests/fingerprint/test_h3_guard.mjs
 *
 * WHY THIS EXISTS
 *
 * http3-fingerprint-spoofing.patch reshapes the H3 SETTINGS frame in
 * neqo-http3, but the QUIC TRANSPORT parameters (neqo-transport: the
 * initial_max_* values, active_connection_id_limit and their ordering, which
 * feed JA4-QUIC) are untouched, and the TLS ClientHello (JA3/JA4) comes from
 * NSS. Claiming Chrome or Safari at the H3 layer therefore ships Chrome
 * SETTINGS with Firefox transport params and a Firefox ClientHello — a
 * layered chimera MORE identifiable than not spoofing at all, the same
 * failure mode as unseeded timer jitter or a JS-only DNT header.
 *
 * CloakfoxPersonas guards this with CROSS_ENGINE_H3 = false. That constant is
 * one edit away from silently re-enabling the chimera, and nothing failed if
 * it flipped, so this pins the behaviour instead of the constant: for every UA
 * shape, the derived profile must ask for the Firefox H3 profile (0).
 *
 * If you are here because you implemented real neqo-transport + TLS
 * spoofing: this test is the thing to update, deliberately, alongside proof
 * that transport params and ClientHello now match the claimed engine.
 *
 * Note the separate reason this is not merely academic: personas normalise
 * every UA to Firefox (normalizeUA), so the non-Firefox branches are
 * unreachable in the default configuration. The guard exists so a MANUAL UA
 * override cannot produce the chimera either.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const SRC = join(root, "additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs");

// The module imports resource:// URLs at the top level, so it cannot be
// imported in plain Node. Extract the real declarations from the shipped
// source and evaluate them, so this tests the shipped code and not a copy.
function extractSource() {
  const text = readFileSync(SRC, "utf8");
  const constMatch = text.match(/^const CROSS_ENGINE_H3 = [^\n]*$/m);
  assert.ok(constMatch, "CROSS_ENGINE_H3 declaration not found — did it move?");

  const fnStart = text.indexOf("export function deriveHttpProfile(");
  assert.ok(fnStart !== -1, "deriveHttpProfile not found — did it move?");
  let i = text.indexOf("{", fnStart);
  let depth = 0;
  for (; i < text.length; i++) {
    if (text[i] === "{") depth++;
    else if (text[i] === "}") { depth--; if (depth === 0) { i++; break; } }
  }
  const fnSrc = text.slice(fnStart, i).replace(/^export\s+/, "");
  return `${constMatch[0]}\n${fnSrc}\nreturn deriveHttpProfile;`;
}

const deriveHttpProfile = new Function(extractSource())();

const UAS = [
  ["Firefox desktop",  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0"],
  ["Firefox Windows",  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"],
  ["Chrome",           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"],
  ["Edge",             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"],
  ["Safari",           "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"],
  ["empty",            ""],
  ["nonsense",         "not-a-user-agent"],
];

test("no UA yields a non-Firefox H3 profile (the chimera guard holds)", () => {
  for (const [label, ua] of UAS) {
    const { h3 } = deriveHttpProfile(ua);
    assert.equal(h3, 0,
      `${label}: h3=${h3}. A non-zero H3 profile ships another engine's ` +
      `SETTINGS frame with Firefox QUIC transport params and a Firefox TLS ` +
      `ClientHello — more identifiable than not spoofing. Only change this ` +
      `alongside real neqo-transport + TLS spoofing.`);
  }
});

test("H2 profile still tracks the UA (the guard is H3-only)", () => {
  // The guard must not have quietly disabled H2 shaping too: H2 SETTINGS are
  // reshaped by http2-fingerprint-spoofing.patch and DO follow the UA.
  assert.equal(deriveHttpProfile(UAS[2][1]).h2, "chrome");
  assert.equal(deriveHttpProfile(UAS[4][1]).h2, "safari");
  assert.equal(deriveHttpProfile(UAS[0][1]).h2, "firefox");
});
