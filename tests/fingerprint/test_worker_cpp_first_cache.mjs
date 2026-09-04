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

function parseHunk(hunk) {
  const header = hunk.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*/);
  assert.ok(header, `invalid unified hunk header: ${hunk.split("\n", 1)[0]}`);
  const oldStart = Number(header[1]);
  const oldCount = header[2] === undefined ? 1 : Number(header[2]);
  const newStart = Number(header[3]);
  const newCount = header[4] === undefined ? 1 : Number(header[4]);
  const oldLines = [];
  const newLines = [];

  for (const line of hunk.slice(header[0].length + 1).split("\n")) {
    if (oldLines.length === oldCount && newLines.length === newCount) break;
    if (line.startsWith("+") && !line.startsWith("+++")) {
      newLines.push(line.slice(1));
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      oldLines.push(line.slice(1));
    } else if (line.startsWith(" ")) {
      oldLines.push(line.slice(1));
      newLines.push(line.slice(1));
    } else if (line === "") {
      // This patch stack contains GNU-patch-compatible bare blank context.
      oldLines.push("");
      newLines.push("");
    } else if (!line.startsWith("\\ No newline at end of file")) {
      break;
    }
  }

  assert.equal(oldLines.length, oldCount,
    `old-side count mismatch in hunk at -${oldStart}`);
  assert.equal(newLines.length, newCount,
    `new-side count mismatch in hunk at +${newStart}`);
  return { oldStart, oldCount, newStart, oldLines, newLines };
}

function hunksInSection(section) {
  return section.split(/\n(?=@@ )/)
    .filter(part => part.startsWith("@@ "))
    .map(parseHunk);
}

function newSideOfHunk(hunk) {
  return parseHunk(hunk).newLines.join("\n");
}

function findSequence(lines, sequence, expected) {
  const matches = [];
  for (let start = 0; start <= lines.length - sequence.length; start++) {
    if (sequence.every((line, offset) => lines[start + offset] === line)) {
      matches.push(start);
    }
  }
  assert.ok(matches.length > 0,
    `patch old side not found near source line ${expected + 1}`);
  return matches.reduce((best, candidate) =>
    Math.abs(candidate - expected) < Math.abs(best - expected) ? candidate : best);
}

function effectivePatchedFile(path) {
  let lines = null;
  for (const patchName of order) {
    const patch = readFileSync(join(patchDir, patchName), "utf8");
    for (const section of patchFileSections(patch, path)) {
      for (const hunk of hunksInSection(section)) {
        if (lines === null) {
          if (hunk.oldStart !== 0 || hunk.oldCount !== 0) continue;
          lines = [];
        }
        const expected = hunk.oldStart === 0 ? 0 : hunk.oldStart - 1;
        const start = hunk.oldLines.length === 0
          ? Math.min(expected, lines.length)
          : findSequence(lines, hunk.oldLines, expected);
        lines.splice(start, hunk.oldLines.length, ...hunk.newLines);
      }
    }
  }
  assert.ok(lines, `no source-of-truth patch creates ${path}`);
  return lines.join("\n");
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
  const result = extractBalanced(effectivePatchedFile(path), signature);
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

function maskCpp(source) {
  const masked = source.split("");
  let state = "code";
  let escaped = false;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    const next = source[i + 1];
    if (state === "line-comment") {
      if (char === "\n") state = "code";
      else masked[i] = " ";
    } else if (state === "block-comment") {
      masked[i] = char === "\n" ? "\n" : " ";
      if (char === "*" && next === "/") {
        masked[i + 1] = " ";
        i++;
        state = "code";
      }
    } else if (state === "string" || state === "character") {
      masked[i] = char === "\n" ? "\n" : " ";
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if ((state === "string" && char === "\"") ||
                 (state === "character" && char === "'")) {
        state = "code";
      }
    } else if (char === "/" && next === "/") {
      masked[i] = masked[i + 1] = " ";
      i++;
      state = "line-comment";
    } else if (char === "/" && next === "*") {
      masked[i] = masked[i + 1] = " ";
      i++;
      state = "block-comment";
    } else if (char === "\"") {
      masked[i] = " ";
      state = "string";
    } else if (char === "'") {
      masked[i] = " ";
      state = "character";
    }
  }
  return masked.join("");
}

function delimiterPairs(masked, open, close) {
  const stack = [];
  const pairs = new Map();
  for (let i = 0; i < masked.length; i++) {
    if (masked[i] === open) stack.push(i);
    if (masked[i] === close) {
      const start = stack.pop();
      assert.notEqual(start, undefined, `unmatched ${close} at ${i}`);
      pairs.set(start, i);
    }
  }
  assert.equal(stack.length, 0, `unmatched ${open} at ${stack.at(-1)}`);
  return pairs;
}

function braceScopes(source) {
  const masked = maskCpp(source);
  return [...delimiterPairs(masked, "{", "}")]
    .map(([start, close]) => ({ start, end: close + 1 }));
}

function innermostScopeAt(scopes, index) {
  return scopes
    .filter(scope => scope.start < index && index < scope.end)
    .sort((a, b) => b.start - a.start)[0];
}

function mutexLifetimes(source) {
  const masked = maskCpp(source);
  const scopes = braceScopes(source);
  const cacheUses = allIndices(masked, /GetLocalCacheMutex\s*\(\s*\)/g);
  const recognizedUses = [];
  const lifetimes = [];
  const declaration = /\bMutexAutoLock\s+\w+\s*(?:\(\s*GetLocalCacheMutex\s*\(\s*\)\s*\)|\{\s*GetLocalCacheMutex\s*\(\s*\)\s*\})\s*;/g;
  for (const match of masked.matchAll(declaration)) {
    recognizedUses.push(match.index + match[0].indexOf("GetLocalCacheMutex"));
    const scope = innermostScopeAt(scopes, match.index);
    assert.ok(scope, "cache mutex declaration must have a lexical scope");
    lifetimes.push({ start: match.index, end: scope.end });
  }
  assert.deepEqual(recognizedUses, cacheUses,
    "unsupported cache mutex use must fail closed");
  return lifetimes;
}

function assertWithinCacheMutex(source, index, message) {
  assert.ok(mutexLifetimes(source).some(lock => lock.start < index && index < lock.end),
    message);
}

function assertOutsideCacheMutex(source, index, message) {
  assert.ok(mutexLifetimes(source).every(lock => index < lock.start || index >= lock.end),
    message);
}

function ifBlocks(source) {
  const masked = maskCpp(source);
  const parens = delimiterPairs(masked, "(", ")");
  const braces = delimiterPairs(masked, "{", "}");
  const blocks = [];
  for (const match of masked.matchAll(/\bif\s*(?=\()/g)) {
    const openParen = masked.indexOf("(", match.index);
    const closeParen = parens.get(openParen);
    assert.notEqual(closeParen, undefined, "if condition must close");
    let openBrace = closeParen + 1;
    while (/\s/.test(masked[openBrace])) openBrace++;
    if (masked[openBrace] !== "{") continue;
    const closeBrace = braces.get(openBrace);
    assert.notEqual(closeBrace, undefined, "if block must close");
    blocks.push({
      start: match.index,
      bodyStart: openBrace,
      end: closeBrace + 1,
      condition: masked.slice(openParen + 1, closeParen),
    });
  }
  return blocks;
}

function assertMainThreadDominates(source, index, expectedCondition, message) {
  const normalizedExpected = expectedCondition.replace(/\s+/g, "");
  const dominated = ifBlocks(source).some(block =>
    block.bodyStart < index && index < block.end &&
    block.condition.replace(/\s+/g, "") === normalizedExpected);
  assert.ok(dominated, message);
}

function validateCppFirstLookup(source) {
  const offThread = blockAt(source, "if (!NS_IsMainThread())");
  assert.match(offThread.source, /GetLocalCache\(\)\.Lookup\(prefName\)/,
    "off-thread branch must read the cpp-first pref-name cache entry");
  const offThreadLookup = offThread.start +
    offThread.source.indexOf("GetLocalCache().Lookup(prefName)");
  assertWithinCacheMutex(source, offThreadLookup,
    "off-thread cache lookup must occur within a live cache mutex scope");
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
  for (const index of restrictedCalls) {
    assertOutsideCacheMutex(source, index,
      "Preferences and IPC access must remain outside every cache mutex scope");
  }

  const assertion = source.indexOf("MOZ_ASSERT(NS_IsMainThread())", offThread.end);
  assert.ok(assertion >= offThread.end && assertion < restrictedCalls[0],
    "debug assertion must pin all native preference/IPC work to the main thread");

  const preferences = source.indexOf("Preferences::GetCString", assertion);
  const ipc = source.indexOf("SendRoverfoxStorageGet", preferences);
  assert.ok(preferences > assertion, "main thread must refresh from Preferences");
  assert.ok(ipc > preferences, "child-process IPC fallback must follow Preferences");

  const remove = source.indexOf("GetLocalCache().Remove(prefName)", ipc);
  const update = source.indexOf("GetLocalCache().InsertOrUpdate(prefName", ipc);
  assert.ok(remove > ipc, "main-thread miss must remove stale cpp-first cache state");
  assert.ok(update > ipc, "main-thread success must update cpp-first cache state");
  assertWithinCacheMutex(source, remove,
    "main-thread cache removal must occur within a live cache mutex scope");
  assertWithinCacheMutex(source, update,
    "main-thread cache population must occur within a live cache mutex scope");
}

function validateGetStringFallback(source) {
  const cacheLookup = source.indexOf("GetLocalCache().Lookup(prefName)");
  assert.ok(cacheLookup >= 0, "GetString must consult the roverfox cache");
  assertWithinCacheMutex(source, cacheLookup,
    "GetString roverfox cache lookup must occur within a live cache mutex scope");

  const preferences = allIndices(source, /Preferences::GetCString/g);
  const ipc = allIndices(source, /SendRoverfoxStorageGet/g);
  assert.equal(preferences.length, 1, "GetString must have one Preferences fallback");
  assert.equal(ipc.length, 1, "GetString must have one IPC fallback");
  assertMainThreadDominates(source, preferences[0],
    "utf8Value.IsEmpty() && NS_IsMainThread()",
    "GetString Preferences fallback must be dominated by NS_IsMainThread");
  assertMainThreadDominates(source, ipc[0],
    "utf8Value.IsEmpty() && !XRE_IsParentProcess() && NS_IsMainThread()",
    "GetString IPC fallback must be dominated by NS_IsMainThread");
  assertOutsideCacheMutex(source, preferences[0],
    "GetString Preferences fallback must remain outside every cache mutex scope");
  assertOutsideCacheMutex(source, ipc[0],
    "GetString IPC fallback must remain outside every cache mutex scope");
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
const getString = effectivePatchedFunction(
  "dom/base/RoverfoxStorageManager.cpp",
  "RoverfoxStorageManager::GetString"
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

test("effective GetString includes both worker-thread guards", () => {
  validateGetStringFallback(getString);
});

test("gate rejects removal of the GetString Preferences main-thread guard", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && NS_IsMainThread())",
    "if (utf8Value.IsEmpty())"
  );
  assert.notEqual(mutant, getString, "Preferences-guard mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /Preferences fallback must be dominated/);
});

test("gate rejects removal of the GetString IPC main-thread guard", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && !XRE_IsParentProcess() && NS_IsMainThread())",
    "if (utf8Value.IsEmpty() && !XRE_IsParentProcess())"
  );
  assert.notEqual(mutant, getString, "IPC-guard mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /IPC fallback must be dominated/);
});

test("gate rejects OR weakening of the GetString Preferences guard", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && NS_IsMainThread())",
    "if (utf8Value.IsEmpty() || NS_IsMainThread())"
  );
  assert.notEqual(mutant, getString, "OR-guard mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /Preferences fallback must be dominated/);
});

test("gate rejects a parenthesized negated main-thread guard", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && NS_IsMainThread())",
    "if (utf8Value.IsEmpty() && !(NS_IsMainThread()))"
  );
  assert.notEqual(mutant, getString, "negated-guard mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /Preferences fallback must be dominated/);
});

test("gate rejects an always-true disjunct in the Preferences guard", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && NS_IsMainThread())",
    "if ((utf8Value.IsEmpty() && NS_IsMainThread()) || true)"
  );
  assert.notEqual(mutant, getString, "always-true mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /Preferences fallback must be dominated/);
});

test("gate rejects unsupported ternary main-thread guard logic", () => {
  const mutant = getString.replace(
    "if (utf8Value.IsEmpty() && NS_IsMainThread())",
    "if (NS_IsMainThread() ? utf8Value.IsEmpty() : true)"
  );
  assert.notEqual(mutant, getString, "ternary-guard mutation did not apply");
  assert.throws(() => validateGetStringFallback(mutant),
    /Preferences fallback must be dominated/);
});

test("gate rejects a closed off-thread cache-lock scope", () => {
  const mutant = lookup.replace(
    "MutexAutoLock lock(GetLocalCacheMutex());\n    if (auto entry",
    "{ MutexAutoLock lock(GetLocalCacheMutex()); }\n    if (auto entry"
  );
  assert.notEqual(mutant, lookup, "off-thread lock-scope mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /off-thread cache lookup/);
});

test("gate rejects closing the main-thread cache lock before Remove", () => {
  const original = `  {
    MutexAutoLock lock(GetLocalCacheMutex());
    if (v.IsEmpty()) {
      GetLocalCache().Remove(prefName);
    } else {
      GetLocalCache().InsertOrUpdate(prefName, nsCString(v));
    }
  }`;
  const replacement = `  if (v.IsEmpty()) {
    GetLocalCache().Remove(prefName);
  } else {
    MutexAutoLock lock(GetLocalCacheMutex());
    GetLocalCache().InsertOrUpdate(prefName, nsCString(v));
  }`;
  const mutant = lookup.replace(original, replacement);
  assert.notEqual(mutant, lookup, "Remove lock-scope mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant),
    /main-thread cache removal/);
});

test("gate rejects closing the main-thread cache lock before Insert", () => {
  const original = `  {
    MutexAutoLock lock(GetLocalCacheMutex());
    if (v.IsEmpty()) {
      GetLocalCache().Remove(prefName);
    } else {
      GetLocalCache().InsertOrUpdate(prefName, nsCString(v));
    }
  }`;
  const replacement = `  if (v.IsEmpty()) {
    MutexAutoLock lock(GetLocalCacheMutex());
    GetLocalCache().Remove(prefName);
  } else {
    GetLocalCache().InsertOrUpdate(prefName, nsCString(v));
  }`;
  const mutant = lookup.replace(original, replacement);
  assert.notEqual(mutant, lookup, "Insert lock-scope mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant),
    /main-thread cache population/);
});

test("gate rejects a cache mutex spanning Preferences and IPC", () => {
  const mutant = lookup.replace(
    "nsAutoCString v;",
    "MutexAutoLock outerLock(GetLocalCacheMutex());\n  nsAutoCString v;"
  );
  assert.notEqual(mutant, lookup, "outer-lock mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /Preferences.*mutex|IPC.*mutex/);
});

test("gate recognizes a brace-init cache mutex spanning Preferences and IPC", () => {
  const mutant = lookup.replace(
    "nsAutoCString v;",
    "MutexAutoLock outerLock{GetLocalCacheMutex()};\n  nsAutoCString v;"
  );
  assert.notEqual(mutant, lookup, "brace-init outer-lock mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /Preferences.*mutex|IPC.*mutex/);
});

test("gate rejects unsupported alias initialization of the cache mutex", () => {
  const mutant = lookup.replace(
    "nsAutoCString v;",
    "auto& cacheMutex = GetLocalCacheMutex();\n  MutexAutoLock outerLock(cacheMutex);\n  nsAutoCString v;"
  );
  assert.notEqual(mutant, lookup, "alias-lock mutation did not apply");
  assert.throws(() => validateCppFirstLookup(mutant), /unsupported cache mutex use/);
});
