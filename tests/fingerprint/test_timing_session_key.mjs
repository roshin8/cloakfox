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
const settingsSrc = readFileSync(
  join(root, "additions/browser/components/cloakfox/content/settings.js"), "utf8"
);
const popupSrc = readFileSync(
  join(root, "additions/browser/extensions/cloakfox-shield/experiment-apis/cloakfox.js"),
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

function extractConstDeclaration(src, name) {
  const start = src.indexOf(`const ${name} =`);
  if (start < 0) throw new Error(`declaration not found: ${name}`);
  const end = src.indexOf(";", start);
  return src.slice(start, end + 1);
}

const settingsU32Block = extractBlock(settingsSrc, /function u32\(/);
const settingsBuildBlock = extractBlock(settingsSrc, /function buildCloakCfg\(/)
  .replace("buildCloakCfg", "buildSettingsCloakCfg");
const settingsPersistBlock = extractBlock(settingsSrc, /function persistCloakCfg\(/)
  .replaceAll("buildCloakCfg", "buildSettingsCloakCfg");
const popupB64Block = extractBlock(popupSrc, /function b64ToBytes\(/);
const popupCharsBlock = extractConstDeclaration(popupSrc, "B64_CHARS");
const popupU32Block = extractBlock(popupSrc, /function u32\(/)
  .replace("function u32", "function popupU32");
const popupBuildBlock = extractBlock(popupSrc, /function buildCloakCfg\(/)
  .replace("buildCloakCfg", "buildPopupCloakCfg")
  .replaceAll("u32(", "popupU32(");

const seedNamesBlock = extractConstDeclaration(seedSyncSrc, "SEED_PREF_NAMES");
const randomBlock = extractBlock(seedSyncSrc, /function randomSeedB64\(/);
const sessionSaltBlock = extractConstDeclaration(seedSyncSrc, "SESSION_TIMING_SALT");
const lifecycleDeriveBlock = extractBlock(
  seedSyncSrc, /export function deriveTimingSessionKey\(/
).replace(/^export\s+/, "");
const lifecycleMergeBlock = extractBlock(
  seedSyncSrc, /export function mergeSessionTimingKey\(/
).replace(/^export\s+/, "");
const rebuildBlock = extractBlock(
  seedSyncSrc, /export function needsCfgRebuild\(/
).replace(/^export\s+/, "");
const ensureBlock = extractBlock(seedSyncSrc, /function ensureContainerSeeds\(/);
const lifecycleMod = await import(
  "data:text/javascript," + encodeURIComponent(`
    const values = new Map();
    let writes = 0;
    const Services = {
      prefs: {
        getStringPref(name, fallback) { return values.get(name) ?? fallback; },
        setStringPref(name, value) { values.set(name, value); writes++; },
        getBoolPref(name, fallback) { return values.get(name) ?? fallback; },
      },
    };
    ${seedNamesBlock}
    ${randomBlock}
    ${sessionSaltBlock}
    ${lifecycleDeriveBlock}
    ${lifecycleMergeBlock}
    ${rebuildBlock}
    ${ensureBlock}
    export function setPrefs(entries) {
      values.clear();
      writes = 0;
      for (const [name, value] of entries) values.set(name, value);
    }
    export function getPref(name) { return values.get(name); }
    export function getWrites() { return writes; }
    export function runEnsure(ucid) { ensureContainerSeeds(ucid); }
  `)
);
const { setPrefs, getPref, getWrites, runEnsure } = lifecycleMod;

const ensureAllBlock = extractBlock(seedSyncSrc, /function ensureSeedsForAllContainers\(/);
const reconciliationStateBlock = seedSyncSrc.match(
  /let reconcilingSessionTiming = false;/
)?.[0];
if (!reconciliationStateBlock) throw new Error("reconciliation state not found");
const observerBlock = extractBlock(seedSyncSrc, /const observer = /);
const observerMod = await import(
  "data:text/javascript," + encodeURIComponent(`
    const values = new Map();
    let writes = 0;
    const publishes = [];
    let observerRef = null;
    function notify(name) {
      observerRef?.observe(null, "nsPref:changed", name);
    }
    const Services = {
      prefs: {
        getStringPref(name, fallback) { return values.get(name) ?? fallback; },
        setStringPref(name, value) { values.set(name, value); writes++; notify(name); },
        clearUserPref(name) { values.delete(name); writes++; notify(name); },
        getBoolPref(name, fallback) { return values.get(name) ?? fallback; },
        setBoolPref(name, value) { values.set(name, value); writes++; notify(name); },
      },
    };
    const ContextualIdentityService = {
      getPublicIdentities() { return [{ userContextId: 9 }]; },
    };
    function applyGenericFontPrefs() {}
    function publish() { publishes.push(Object.fromEntries(values)); }
    const fillPersonaKeys = (seed, ucid) => ({
      "fonts": ["Arial"], "navigator.userAgent": "settings-" + ucid,
    });
    const writeHttpProfilePrefs = () => {};
    const cloakCfgPref = (ucid) => "cloakfox.s.cloak_cfg_" + ucid;
    const ChromeUtils = {
      importESModule(path) {
        if (path.includes("CloakfoxPersonas")) return { fillPersonaKeys };
        return { applyOverrides: (_ucid, base) => ({
          ...base, "navigator.hardwareConcurrency": 24, "popup:override": true,
        }) };
      },
    };
    ${seedNamesBlock}
    ${randomBlock}
    ${sessionSaltBlock}
    ${lifecycleDeriveBlock}
    ${lifecycleMergeBlock}
    ${rebuildBlock}
    ${ensureBlock}
    ${ensureAllBlock}
    ${reconciliationStateBlock}
    ${observerBlock}
    ${settingsU32Block}
    ${settingsBuildBlock}
    ${settingsPersistBlock}
    ${popupCharsBlock}
    ${popupB64Block}
    ${popupU32Block}
    ${popupBuildBlock}
    observerRef = observer;
    export function setPrefs(entries) {
      values.clear();
      writes = 0;
      publishes.length = 0;
      for (const [name, value] of entries) values.set(name, value);
    }
    export function getPref(name) { return values.get(name); }
    export function getWrites() { return writes; }
    export function getPublishes() { return publishes; }
    export function clearEvents() { writes = 0; publishes.length = 0; }
    export function runEnsure(ucid) { ensureContainerSeeds(ucid); }
    export function writeSettings(ucid, seed) { persistCloakCfg(ucid, seed); }
    export function writePopup(ucid, seed) {
      const cfg = buildPopupCloakCfg(seed, ucid);
      Services.prefs.setStringPref("cloakfox.container." + ucid + ".math_seed", seed);
      Services.prefs.setStringPref(cloakCfgPref(ucid), cfg);
    }
    export function clearSettings(ucid, overridePrefs) {
      Services.prefs.clearUserPref("cloakfox.container." + ucid + ".math_seed");
      Services.prefs.clearUserPref(cloakCfgPref(ucid));
      Services.prefs.clearUserPref("cloakfox.container." + ucid + ".timezone");
      Services.prefs.clearUserPref("cloakfox.container." + ucid + ".persona_index");
      for (const pref of overridePrefs) Services.prefs.clearUserPref(pref);
    }
    export function setEnabled(value) { Services.prefs.setBoolPref("cloakfox.enabled", value); }
    export function setString(name, value) { Services.prefs.setStringPref(name, value); }
  `)
);
const {
  setPrefs: setObserverPrefs,
  getPref: getObserverPref,
  getWrites: getObserverWrites,
  getPublishes: getObserverPublishes,
  clearEvents: clearObserverEvents,
  runEnsure: runObserverEnsure,
  writeSettings,
  writePopup,
  clearSettings,
  setEnabled,
  setString: setObserverString,
} = observerMod;

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

function validCfg(extra = {}) {
  return JSON.stringify({
    "canvas:seed": 7,
    "fonts": ["Arial"],
    "fonts:spacing_seed": 8,
    ...extra,
  });
}

function validSeed(byte) {
  return Buffer.from(new Uint8Array(32).fill(byte)).toString("base64");
}

test("disabled lifecycle leaves container timing prefs and config untouched", () => {
  const cfg = validCfg({"timing:session_key_hi": 1, "timing:session_key_lo": 2});
  setPrefs([
    ["cloakfox.enabled", false],
    ["cloakfox.container.4.math_seed", validSeed(1)],
    ["cloakfox.container.4.keyboard_seed", validSeed(2)],
    ["cloakfox.container.4.timing_seed", validSeed(3)],
    ["cloakfox.s.cloak_cfg_4", cfg],
  ]);
  runEnsure(4);
  assert.equal(getWrites(), 0);
  assert.equal(getPref("cloakfox.s.cloak_cfg_4"), cfg);
});

test("invalid timing seed is repaired before replacing stale session key", () => {
  setPrefs([
    ["cloakfox.enabled", true],
    ["cloakfox.container.5.math_seed", validSeed(1)],
    ["cloakfox.container.5.keyboard_seed", validSeed(2)],
    ["cloakfox.container.5.timing_seed", "not valid base64"],
    ["cloakfox.s.cloak_cfg_5", validCfg({
      "timing:session_key_hi": 1, "timing:session_key_lo": 2,
    })],
  ]);
  runEnsure(5);
  assert.equal(atob(getPref("cloakfox.container.5.timing_seed")).length, 32);
  const cfg = JSON.parse(getPref("cloakfox.s.cloak_cfg_5"));
  assert.notEqual(cfg["timing:session_key_hi"], 1);
  assert.notEqual(cfg["timing:session_key_lo"], 2);
});

test("missing timing seed is installed before a session key is written", () => {
  setPrefs([
    ["cloakfox.enabled", true],
    ["cloakfox.container.7.math_seed", validSeed(1)],
    ["cloakfox.container.7.keyboard_seed", validSeed(2)],
    ["cloakfox.s.cloak_cfg_7", validCfg()],
  ]);
  runEnsure(7);
  assert.equal(atob(getPref("cloakfox.container.7.timing_seed")).length, 32);
  const cfg = JSON.parse(getPref("cloakfox.s.cloak_cfg_7"));
  assert.equal(typeof cfg["timing:session_key_hi"], "number");
  assert.equal(typeof cfg["timing:session_key_lo"], "number");
});

test("one launch keeps a stable session key and avoids a duplicate config write", () => {
  setPrefs([
    ["cloakfox.enabled", true],
    ["cloakfox.container.6.math_seed", validSeed(1)],
    ["cloakfox.container.6.keyboard_seed", validSeed(2)],
    ["cloakfox.container.6.timing_seed", validSeed(3)],
    ["cloakfox.s.cloak_cfg_6", validCfg()],
  ]);
  runEnsure(6);
  const firstCfg = getPref("cloakfox.s.cloak_cfg_6");
  const writesAfterFirstPass = getWrites();
  runEnsure(6);
  assert.equal(getPref("cloakfox.s.cloak_cfg_6"), firstCfg);
  assert.equal(getWrites(), writesAfterFirstPass);
});

function activeObserverPrefs(ucid, cfg) {
  return [
    ["cloakfox.enabled", true],
    [`cloakfox.container.${ucid}.math_seed`, validSeed(1)],
    [`cloakfox.container.${ucid}.keyboard_seed`, validSeed(2)],
    [`cloakfox.container.${ucid}.timing_seed`, validSeed(3)],
    [`cloakfox.s.cloak_cfg_${ucid}`, cfg],
  ];
}

test("settings cloak_cfg rewrite retains the current launch session key", () => {
  setObserverPrefs(activeObserverPrefs(12, validCfg()));
  runObserverEnsure(12);
  const originalKey = JSON.parse(getObserverPref("cloakfox.s.cloak_cfg_12"));
  clearObserverEvents();

  writeSettings(12, validSeed(4));

  const repaired = JSON.parse(getObserverPref("cloakfox.s.cloak_cfg_12"));
  assert.equal(repaired["navigator.userAgent"], "settings-12");
  assert.equal(repaired["timing:session_key_hi"], originalKey["timing:session_key_hi"]);
  assert.equal(repaired["timing:session_key_lo"], originalKey["timing:session_key_lo"]);
  assert.equal(getObserverWrites(), 2);
  assert.equal(getObserverPublishes().length, 1);
  assert.ok(getObserverPublishes().every((snapshot) => {
    const cfg = JSON.parse(snapshot["cloakfox.s.cloak_cfg_12"]);
    return typeof cfg["timing:session_key_hi"] === "number" &&
      typeof cfg["timing:session_key_lo"] === "number";
  }));
});

test("popup cloak_cfg rewrite retains the current launch session key", () => {
  setObserverPrefs(activeObserverPrefs(13, validCfg()));
  runObserverEnsure(13);
  const originalKey = JSON.parse(getObserverPref("cloakfox.s.cloak_cfg_13"));
  clearObserverEvents();

  writePopup(13, validSeed(5));

  const repaired = JSON.parse(getObserverPref("cloakfox.s.cloak_cfg_13"));
  assert.equal(repaired["popup:override"], true);
  assert.equal(repaired["navigator.hardwareConcurrency"], 24);
  assert.equal(repaired["timing:session_key_hi"], originalKey["timing:session_key_hi"]);
  assert.equal(repaired["timing:session_key_lo"], originalKey["timing:session_key_lo"]);
  assert.equal(getObserverWrites(), 3);
  assert.equal(getObserverPublishes().length, 2);
  assert.ok(getObserverPublishes().every((snapshot) => {
    const cfg = JSON.parse(snapshot["cloakfox.s.cloak_cfg_13"]);
    return typeof cfg["timing:session_key_hi"] === "number" &&
      typeof cfg["timing:session_key_lo"] === "number";
  }));
});

test("live enable seeds default and public containers and installs session keys", () => {
  setObserverPrefs([
    ["cloakfox.enabled", false],
    ["cloakfox.s.cloak_cfg_0", validCfg({"canvas:seed": 70})],
    ["cloakfox.s.cloak_cfg_9", validCfg({"canvas:seed": 79})],
  ]);
  clearObserverEvents();
  setEnabled(true);
  for (const ucid of [0, 9]) {
    assert.equal(atob(getObserverPref(`cloakfox.container.${ucid}.timing_seed`)).length, 32);
    const cfg = JSON.parse(getObserverPref(`cloakfox.s.cloak_cfg_${ucid}`));
    assert.equal(typeof cfg["timing:session_key_hi"], "number");
    assert.equal(typeof cfg["timing:session_key_lo"], "number");
  }
  assert.ok(getObserverPublishes().every((snapshot) => {
    if (!snapshot["cloakfox.enabled"]) return true;
    return [0, 9].every((ucid) => {
      const cfg = JSON.parse(snapshot[`cloakfox.s.cloak_cfg_${ucid}`]);
      return typeof cfg["timing:session_key_hi"] === "number" &&
        typeof cfg["timing:session_key_lo"] === "number";
    });
  }));
});

test("settings Clear leaves config absent and removes its override state", () => {
  const override = "cloakfox.override.14.navigator.hardwareConcurrency";
  setObserverPrefs([
    ...activeObserverPrefs(14, validCfg()),
    [override, "16"],
    ["cloakfox.container.14.timezone", "UTC"],
  ]);
  clearObserverEvents();
  clearSettings(14, [override]);

  assert.equal(getObserverPref("cloakfox.container.14.math_seed"), undefined);
  assert.equal(getObserverPref("cloakfox.s.cloak_cfg_14"), undefined);
  assert.equal(getObserverPref(override), undefined);
  assert.ok(getObserverPublishes().some(
    (snapshot) => !("cloakfox.s.cloak_cfg_14" in snapshot)
  ));
});

test("unrelated pref changes do not reseed a container", () => {
  setObserverPrefs(activeObserverPrefs(15, validCfg()));
  runObserverEnsure(15);
  const cfg = getObserverPref("cloakfox.s.cloak_cfg_15");
  clearObserverEvents();
  setObserverString("cloakfox.opt.unrelated", "value");
  assert.equal(getObserverPref("cloakfox.s.cloak_cfg_15"), cfg);
  assert.equal(getObserverWrites(), 1);
});

test("unchanged timing seed retains its current-launch key", () => {
  setObserverPrefs(activeObserverPrefs(16, validCfg()));
  runObserverEnsure(16);
  const cfg = getObserverPref("cloakfox.s.cloak_cfg_16");
  const seed = getObserverPref("cloakfox.container.16.timing_seed");
  clearObserverEvents();
  setObserverString("cloakfox.container.16.timing_seed", seed);
  assert.equal(getObserverPref("cloakfox.s.cloak_cfg_16"), cfg);
  assert.equal(getObserverWrites(), 1);
});
