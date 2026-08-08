/* Unit tests for the SeedSync/Personas font fixes: #7 (generic-font union that
 * resolves each OS to its own persona generic + C++ whitelist consistency) and
 * #8 (needsCfgRebuild). The source modules import resource:// URLs at the top
 * level, so they can't be imported directly in Node — we extract the pure
 * declarations from the real source text and evaluate them (testing the shipped
 * code, not a copy).
 *
 *   node --test tests/fingerprint/test_seedsync_fonts.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");

// Extract a top-level `const NAME = {...};` or `function NAME(...) {...}` block
// by brace-balancing from the first `{` after the declaration keyword.
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
const personasSrc = readFileSync(
  join(root, "additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs"),
  "utf8"
);
const fontHijackerPatch = readFileSync(
  join(root, "patches/font-hijacker.patch"),
  "utf8"
);

// Build a module exposing the pure helpers from the real source text.
const rebuildBlock = extractBlock(seedSyncSrc, /export function needsCfgRebuild\(/)
  .replace(/^export\s+/, "");
const canonicalBlock = extractBlock(personasSrc, /const CANONICAL_FONTS = /);
const genericBlock = extractBlock(personasSrc, /const GENERIC_FONTS = /);
const unionBlock = extractBlock(personasSrc, /export function genericFontListUnion\(\)/)
  .replace(/^export\s+/, "");

const mod = await import(
  "data:text/javascript," +
  encodeURIComponent(
    `${rebuildBlock}\n${canonicalBlock}\n${genericBlock}\n${unionBlock}\n` +
    "export { needsCfgRebuild, CANONICAL_FONTS, GENERIC_FONTS, genericFontListUnion };"
  )
);
const { needsCfgRebuild, CANONICAL_FONTS, GENERIC_FONTS, genericFontListUnion } = mod;

const SLOTS = { serif: "serif", sans: "sans", mono: "mono" };

test("#7 each OS resolves its OWN persona generic from the union", () => {
  // The container's per-container filter admits only fonts in that OS's
  // CANONICAL set; the FIRST union member it admits is what renders. That must
  // equal GENERIC_FONTS[os][slot] — i.e. the union ORDER is correct per OS.
  const union = genericFontListUnion();
  for (const os of ["macos", "windows", "linux"]) {
    const allow = new Set([
      ...CANONICAL_FONTS[os].base, ...CANONICAL_FONTS[os].optional,
    ]);
    for (const slot of Object.keys(SLOTS)) {
      const firstAdmitted = union[slot].split(", ").find((f) => allow.has(f));
      assert.equal(
        firstAdmitted, GENERIC_FONTS[os][slot],
        `${os}/${slot}: union resolves ${firstAdmitted}, want ${GENERIC_FONTS[os][slot]}`
      );
    }
  }
});

test("#7 every union family is kept in the C++ global whitelist", () => {
  // font-hijacker.patch must whitelist every union family, else ApplyWhitelist()
  // deletes it from mFontFamilies and the per-container fallback can't resolve
  // it. Assert each appears in the patch's appended whitelist string.
  const union = genericFontListUnion();
  const families = new Set();
  for (const slot of Object.keys(SLOTS)) {
    for (const f of union[slot].split(", ")) families.add(f);
  }
  for (const fam of families) {
    assert.ok(
      fontHijackerPatch.includes(fam),
      `font-hijacker.patch does not whitelist union family "${fam}"`
    );
  }
});

test("#7 union has no duplicate families within a slot", () => {
  const union = genericFontListUnion();
  for (const slot of Object.keys(SLOTS)) {
    const parts = union[slot].split(", ");
    assert.equal(new Set(parts).size, parts.length, `dup in ${slot}: ${union[slot]}`);
  }
});

test("#8 rebuild when cfg is absent", () => {
  assert.equal(needsCfgRebuild(""), true);
  assert.equal(needsCfgRebuild(undefined), true);
});

test("#8 rebuild when cfg predates the font keys", () => {
  // Old persona: has canvas/audio but no fonts / fonts:spacing_seed.
  assert.equal(needsCfgRebuild(JSON.stringify({ "canvas:seed": 1 })), true);
  assert.equal(needsCfgRebuild(JSON.stringify({ "fonts": ["Arial"] })), true); // missing spacing
  assert.equal(
    needsCfgRebuild(JSON.stringify({ "fonts:spacing_seed": 5 })), true // missing fonts
  );
});

test("#8 corrupt cfg triggers rebuild", () => {
  assert.equal(needsCfgRebuild("{not valid json"), true);
});

test("#8 valid-but-non-object JSON rebuilds instead of throwing", () => {
  // JSON.parse succeeds for these; `"fonts" in null/number/bool/string` would
  // throw a TypeError and leave the container permanently un-rebuilt. Must not
  // throw, must return true.
  for (const bad of ["null", "123", "true", "false", '"a string"', "[1,2,3]"]) {
    assert.doesNotThrow(() => needsCfgRebuild(bad), `threw on ${bad}`);
    assert.equal(needsCfgRebuild(bad), true, `should rebuild on ${bad}`);
  }
});

test("#8 up-to-date cfg is left alone (no clobber)", () => {
  const cfg = JSON.stringify({
    "canvas:seed": 1, "fonts": ["Arial"], "fonts:spacing_seed": 42,
  });
  assert.equal(needsCfgRebuild(cfg), false);
});
