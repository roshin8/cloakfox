/* Regression gate for worker-safe cpp-first configuration reads.
 *
 *   node --test tests/fingerprint/test_worker_cpp_first_cache.mjs
 *
 * Firefox Preferences and ContentChild IPC are main-thread-only. Performance
 * objects for workers are constructed on the worker thread, so their
 * MaskConfig lookup must consume the value cached by WorkerPrivate::Constructor
 * instead of entering either main-thread-only API.
 *
 * This test reconstructs the latest complete TryGetCppFirstPref definition in
 * patch application order. That makes it exercise the effective source-of-
 * truth stack without requiring the generated firefox-src tree in unit CI.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const patchDir = join(root, "patches");
const order = readFileSync(join(patchDir, "order.txt"), "utf8")
  .split("\n")
  .map(line => line.replace(/#.*/, "").trim())
  .filter(Boolean);

function patchFileSections(patch, path) {
  const marker = `+++ b/${path}`;
  const sections = [];
  let cursor = 0;
  while ((cursor = patch.indexOf(marker, cursor)) !== -1) {
    const start = patch.lastIndexOf("\n--- ", cursor) + 1;
    let end = patch.indexOf("\n--- ", cursor + marker.length);
    if (end === -1) end = patch.length;
    sections.push(patch.slice(start, end));
    cursor += marker.length;
  }
  return sections;
}

function newSideOfHunk(hunk) {
  return hunk.split("\n").slice(1).flatMap(line => {
    if (line.startsWith("+") && !line.startsWith("+++")) return [line.slice(1)];
    if (line.startsWith(" ")) return [line.slice(1)];
    return [];
  }).join("\n");
}

function extractBalanced(source, signature) {
  const start = source.indexOf(signature);
  if (start < 0) return null;
  const open = source.indexOf("{", start);
  if (open < 0) return null;
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}" && --depth === 0) return source.slice(start, i + 1);
  }
  return null;
}

function effectivePatchedFunction(path, signature) {
  let result = null;
  for (const patchName of order) {
    const patch = readFileSync(join(patchDir, patchName), "utf8");
    for (const section of patchFileSections(patch, path)) {
      for (const hunk of section.split(/\n(?=@@ )/).filter(part => part.startsWith("@@ "))) {
        const candidate = extractBalanced(newSideOfHunk(hunk), signature);
        if (candidate) result = candidate;
      }
    }
  }
  assert.ok(result, `no complete effective patch definition found for ${signature}`);
  return result;
}

function effectivePatchedHunk(path, marker) {
  let result = null;
  for (const patchName of order) {
    const patch = readFileSync(join(patchDir, patchName), "utf8");
    for (const section of patchFileSections(patch, path)) {
      for (const hunk of section.split(/\n(?=@@ )/).filter(part => part.startsWith("@@ "))) {
        const candidate = newSideOfHunk(hunk);
        if (candidate.includes(marker)) result = candidate;
      }
    }
  }
  assert.ok(result, `no effective patch hunk found for ${marker}`);
  return result;
}

function blockAt(source, marker) {
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `missing control-flow marker: ${marker}`);
  const open = source.indexOf("{", start);
  assert.notEqual(open, -1, `missing block after: ${marker}`);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}" && --depth === 0) {
      return { start, end: i + 1, source: source.slice(start, i + 1) };
    }
  }
  throw new Error(`unterminated block after: ${marker}`);
}

function allIndices(source, pattern) {
  return [...source.matchAll(pattern)].map(match => match.index);
}

function validateCppFirstLookup(source) {
  const offThread = blockAt(source, "if (!NS_IsMainThread())");
  assert.match(offThread.source, /MutexAutoLock\s+\w+\s*\(GetLocalCacheMutex\(\)\)/,
    "off-thread cache lookup must hold the cache mutex");
  assert.match(offThread.source, /GetLocalCache\(\)\.Lookup\(prefName\)/,
    "off-thread branch must read the cpp-first pref-name cache entry");
  assert.match(offThread.source, /outValue\s*=\s*\w+\.Data\(\)/,
    "off-thread cache hit must supply the caller's value");
  assert.match(offThread.source, /return false\s*;/,
    "off-thread cache miss must leave cpp-first lookup without native access");
  assert.doesNotMatch(offThread.source,
    /Preferences::|ContentChild::|SendRoverfoxStorageGet|XRE_IsParentProcess/,
    "off-thread branch may only touch the mutex-protected cache");

  const restrictedCalls = allIndices(source,
    /Preferences::|ContentChild::|SendRoverfoxStorageGet|XRE_IsParentProcess/g);
  assert.ok(restrictedCalls.length >= 4, "expected Preferences and IPC fallback calls");
  assert.ok(restrictedCalls.every(index => index > offThread.end),
    "off-thread return must precede every Preferences and IPC call");

  const assertion = source.indexOf("MOZ_ASSERT(NS_IsMainThread())", offThread.end);
  assert.ok(assertion >= offThread.end && assertion < restrictedCalls[0],
    "debug assertion must pin all native preference/IPC work to the main thread");

  const preferences = source.indexOf("Preferences::GetCString", assertion);
  const ipc = source.indexOf("SendRoverfoxStorageGet", preferences);
  assert.ok(preferences > assertion, "main thread must refresh from Preferences");
  assert.ok(ipc > preferences, "child-process IPC fallback must follow Preferences");

  const refresh = source.slice(ipc);
  const refreshLock = refresh.search(/MutexAutoLock\s+\w+\s*\(GetLocalCacheMutex\(\)\)/);
  const remove = refresh.indexOf("GetLocalCache().Remove(prefName)");
  const update = refresh.indexOf("GetLocalCache().InsertOrUpdate(prefName");
  assert.ok(refreshLock >= 0, "main-thread refresh must lock the shared cache");
  assert.ok(remove > refreshLock,
    "main-thread miss must remove a stale cpp-first cache entry under the lock");
  assert.ok(update > refreshLock,
    "main-thread success must update the cpp-first cache entry under the lock");
}

function validateWorkerWarmup(source) {
  const guard = blockAt(source, "if (NS_IsMainThread())");
  assert.match(guard.source, /AppendPrintf\("cloak_cfg_%u"[\s\S]*mUserContextId\)/,
    "WorkerPrivate must form cloak_cfg_<worker userContextId>");
  assert.match(guard.source, /RoverfoxStorageManager::GetString\(cfgKey,\s*ignored\)/,
    "WorkerPrivate must refresh the exact cpp-first key workers later acquire");
}

const lookup = effectivePatchedFunction(
  "dom/base/RoverfoxStorageManager.cpp",
  "RoverfoxStorageManager::TryGetCppFirstPref"
);
const constructorWarmup = effectivePatchedHunk(
  "dom/workers/WorkerPrivate.cpp",
  "cfgKey.AppendPrintf(\"cloak_cfg_%u\""
);

test("cpp-first lookup is worker-safe and refreshes its shared cache", () => {
  validateCppFirstLookup(lookup);
});

test("WorkerPrivate warms the worker's exact container config", () => {
  validateWorkerWarmup(constructorWarmup);
});

test("gate rejects removal of the off-thread guard", () => {
  const mutant = lookup.replace("if (!NS_IsMainThread())", "if (false)");
  assert.notEqual(mutant, lookup, "guard mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /NS_IsMainThread/);
});

test("gate rejects removal of main-thread cpp-first cache population", () => {
  const mutant = lookup.replace(
    /\s*GetLocalCache\(\)\.InsertOrUpdate\(prefName,[^;]+\);/,
    ""
  );
  assert.notEqual(mutant, lookup, "cache-population mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /success must update/);
});

test("gate rejects removal of stale-cache invalidation", () => {
  const mutant = lookup.replace(
    /\s*GetLocalCache\(\)\.Remove\(prefName\);/,
    ""
  );
  assert.notEqual(mutant, lookup, "cache-invalidation mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /miss must remove/);
});
