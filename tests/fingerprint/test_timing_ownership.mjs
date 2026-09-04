/* Regression gates for native performance-clock ownership and actor timers.
 *
 *   node --test tests/fingerprint/test_timing_ownership.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const timingActor = readFileSync(
  join(root, "additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs"),
  "utf8"
);
const performancePatch = readFileSync(
  join(root, "patches/performance-timeline-timing.patch"),
  "utf8"
);

function extractBalancedBlock(source, start) {
  const open = source.indexOf("{", start);
  if (open < 0) throw new Error("block opening brace not found");
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error("unbalanced block");
}

function extractPatchedFunction(patch, signature) {
  const signatureStart = patch.indexOf(signature);
  if (signatureStart < 0) throw new Error(`patch hunk not found: ${signature}`);
  const hunkStart = patch.lastIndexOf("@@", signatureStart);
  const hunkEnd = patch.indexOf("\n@@", signatureStart);
  const hunk = patch.slice(hunkStart, hunkEnd < 0 ? patch.length : hunkEnd);
  const [header, ...lines] = hunk.split("\n");
  if (!header.includes(`${signature} {`)) {
    throw new Error(`patch hunk header does not declare: ${signature}`);
  }
  return lines.filter(line => line.startsWith("+")).map(line => line.slice(1)).join("\n");
}

function stripJsComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function extractActorWrapper(actorCode, original) {
  const originalDecl = `const ${original} =`;
  const originalStart = actorCode.indexOf(originalDecl);
  if (originalStart < 0) throw new Error(`${originalDecl} not found`);
  const wrapperStart = actorCode.indexOf("Cu.exportFunction(function", originalStart);
  if (wrapperStart < 0) throw new Error(`${original} wrapper not found`);
  return extractBalancedBlock(actorCode, wrapperStart);
}

function assertGeckoOwnsPerformanceNow(patch, actor) {
  const now = extractPatchedFunction(patch, "DOMHighResTimeStamp Performance::Now()");
  assert.match(now, /const\s+DOMHighResTimeStamp\s+reduced\s*=\s*\n\s*nsRFPService::ReduceTimePrecisionAsMSecs\(\s*\n\s*rawTime,\s*GetRandomTimelineSeed\(\),\s*mRTPCallerType\);/);
  assert.match(now, /const\s+DOMHighResTimeStamp\s+reduced[\s\S]*?\n\s*return\s+PresentTimestamp\(reduced\);/);
  assert.equal((now.match(/return\s+PresentTimestamp\s*\(\s*reduced\s*\)/g) || []).length, 1,
    "Performance::Now must present its one reduced timestamp exactly once");
  assert.doesNotMatch(now, /return\s+nsRFPService::ReduceTimePrecisionAsMSecs\s*\(/,
    "Performance::Now must not return an unpresented reduced clock");

  const actorCode = stripJsComments(actor);
  assert.doesNotMatch(actorCode, /\bperformance\s*(?:\.\s*now|\[\s*["']now["']\s*\])/,
    "timing actor must not access a performance.now alias");
  assert.doesNotMatch(actorCode, /\b(?:pageWin|win)\s*(?:\.\s*performance|\[\s*["']performance["']\s*\])\s*(?:\.\s*now|\[\s*["']now["']\s*\])/,
    "timing actor must not access page performance.now");
  assert.doesNotMatch(actorCode, /\bPerformance\s*(?:\.\s*prototype|\[\s*["']prototype["']\s*\])/,
    "timing actor must not access Performance.prototype");
  assert.doesNotMatch(actorCode, /\borigPerfNow\b/,
    "timing actor must not retain a performance.now original");
  assert.doesNotMatch(actorCode, /\b(?:Object\s*\.\s*)?defineProperty\s*\(\s*[^,]*(?:\bperformance\b|\bPerformance\b)[^,]*,\s*["']now["']/,
    "timing actor must not define a performance.now replacement");
}

function assertActorRetainsTimerPaths(actor) {
  const actorCode = stripJsComments(actor);
  assert.match(actorCode, /function\s+makePRNG\s*\(\s*seedBytes\s*\)/,
    "timing actor must retain the shared PRNG definition");
  assert.match(actorCode, /const\s+prng\s*=\s*makePRNG\s*\(\s*b64ToBytes\s*\(\s*seedB64\s*\)\s*\)/,
    "timer paths must share the per-container PRNG");

  for (const { api, original } of [
    { api: "setTimeout", original: "origSetTimeout" },
    { api: "setInterval", original: "origSetInterval" },
    { api: "requestAnimationFrame", original: "origRAF" },
  ]) {
    assert.match(actorCode,
      new RegExp(`pageWin\\.${api}\\s*=\\s*setNativeIdentity\\s*\\(\\s*Cu\\.exportFunction`),
      `${api} must install its page wrapper`);
    const wrapper = extractActorWrapper(actorCode, original);
    assert.match(wrapper, new RegExp(`\\b${original}\\.call\\s*\\(`),
      `${api} wrapper must delegate to ${original}`);
    assert.match(wrapper, /\bprng\s*\(\s*\)/,
      `${api} wrapper must consume the shared PRNG`);
  }
}

test("Gecko owns the reduced performance.now presentation path", () => {
  assertGeckoOwnsPerformanceNow(performancePatch, timingActor);
});

test("timing actor retains all seeded timer and rAF paths", () => {
  assertActorRetainsTimerPaths(timingActor);
});

test("ownership gate rejects a page-clock actor mutation", () => {
  const clockMutant = timingActor.replace(
    "const pageWin = win.wrappedJSObject;",
    "const pageWin = win.wrappedJSObject;\n    pageWin.performance.now;"
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(performancePatch, clockMutant),
    /performance\.now/);
});

test("timer gate rejects an interval path that bypasses the shared PRNG", () => {
  const intervalStart = timingActor.indexOf("const origSetInterval =");
  const before = timingActor.slice(0, intervalStart);
  const after = timingActor.slice(intervalStart).replace("prng()", "0");
  assert.throws(() => assertActorRetainsTimerPaths(before + after),
    /setInterval wrapper must consume the shared PRNG/);
});
