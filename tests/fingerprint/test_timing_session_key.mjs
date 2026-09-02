/* Unit tests for per-container, per-launch timing session keys. The source
 * module imports resource:// URLs at top level, so extract the pure functions
 * from shipped source and evaluate them in Node.
 *
 *   node --test tests/fingerprint/test_timing_session_key.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");

function extractBlock(src, startRe) {
  const m = startRe.exec(src);
  if (!m) throw new Error(`declaration not found: ${startRe}`);
  const open = src.indexOf("{", m.index);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(m.index, i + 1);
    }
  }
  throw new Error("unbalanced braces");
}

const seedSyncSrc = readFileSync(
  join(root, "additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs"),
  "utf8"
);
const deriveBlock = extractBlock(
  seedSyncSrc, /export function deriveTimingSessionKey\(/
).replace(/^export\s+/, "");
const mergeBlock = extractBlock(
  seedSyncSrc, /export function mergeSessionTimingKey\(/
).replace(/^export\s+/, "");
const mod = await import(
  "data:text/javascript," + encodeURIComponent(
    `${deriveBlock}\n${mergeBlock}\n` +
    "export { deriveTimingSessionKey, mergeSessionTimingKey };"
  )
);
const { deriveTimingSessionKey, mergeSessionTimingKey } = mod;

const SEED_A = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
const SEED_B = "Hy4dHBsaGRgXFhUUExIREA8ODQwLCgkIBwYFBAMCAQA=";
const SALT_A = "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8=";
const SALT_B = "QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZXWFlaW1xdXl8=";

test("session timing key is deterministic for one seed and salt", () => {
  assert.deepEqual(deriveTimingSessionKey(SEED_A, SALT_A),
                   deriveTimingSessionKey(SEED_A, SALT_A));
});

test("session timing key changes with container seed and launch salt", () => {
  assert.notDeepEqual(deriveTimingSessionKey(SEED_A, SALT_A),
                      deriveTimingSessionKey(SEED_B, SALT_A));
  assert.notDeepEqual(deriveTimingSessionKey(SEED_A, SALT_A),
                      deriveTimingSessionKey(SEED_A, SALT_B));
});

test("session merge overwrites stale timing words and preserves persona keys", () => {
  const merged = JSON.parse(mergeSessionTimingKey(
    JSON.stringify({"canvas:seed": 7, "timing:session_key_hi": 1}),
    {hi: 0x12345678, lo: 0x90abcdef}
  ));
  assert.equal(merged["canvas:seed"], 7);
  assert.equal(merged["timing:session_key_hi"], 0x12345678);
  assert.equal(merged["timing:session_key_lo"], 0x90abcdef);
});
