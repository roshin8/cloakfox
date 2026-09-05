/* Structural regression gate for the WorkerPrivate timing-mask lifecycle.
 *
 *   node --test tests/fingerprint/test_sab_worker_timing_lifecycle.mjs
 *
 * This inspects individual source-patch functions and call-site hunks. Global
 * token counts are deliberately insufficient: removing any start/stop site,
 * callback lookup, or failed-arm cleanup must fail the corresponding check.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const patch = readFileSync(
  join(root, "patches", "sab-worker-timing-masking.patch"), "utf8");

function patchFileSections(path) {
  const marker = `+++ b/${path}`;
  const sections = [];
  let cursor = 0;
  while ((cursor = patch.indexOf(marker, cursor)) !== -1) {
    const start = patch.lastIndexOf("\n--- ", cursor) + 1;
    let end = patch.indexOf("\ndiff --git ", cursor + marker.length);
    if (end === -1) end = patch.length;
    sections.push(patch.slice(start, end));
    cursor += marker.length;
  }
  return sections;
}

function newSideHunks(path) {
  return patchFileSections(path).flatMap(section =>
    section.split(/\n(?=@@ )/)
      .filter(part => part.startsWith("@@ "))
      .map(hunk => hunk.split("\n").slice(1)
        .filter(line => !line.startsWith("-"))
        .map(line => line.startsWith("+") || line.startsWith(" ")
          ? line.slice(1)
          : line)
        .join("\n")));
}

const cppHunks = newSideHunks("dom/workers/WorkerPrivate.cpp");
const added = cppHunks.join("\n");
const headerAdded = newSideHunks("dom/workers/WorkerPrivate.h").join("\n");

function hunkContaining(marker) {
  const matches = cppHunks.filter(hunk => hunk.includes(marker));
  assert.equal(matches.length, 1, `expected one WorkerPrivate.cpp hunk containing ${marker}`);
  return matches[0];
}

function functionBody(signature) {
  const start = added.indexOf(signature);
  assert.notEqual(start, -1, `missing ${signature}`);
  const open = added.indexOf("{", start);
  assert.notEqual(open, -1, `missing body for ${signature}`);
  let depth = 0;
  for (let i = open; i < added.length; i++) {
    if (added[i] === "{") depth++;
    if (added[i] === "}" && --depth === 0) return added.slice(open + 1, i);
  }
  assert.fail(`unterminated body for ${signature}`);
}

test("eligible workers cache one validated timing state before the run loop", () => {
  const eligibility = functionBody(
    "bool WorkerPrivate::ShouldUseCloakfoxTimingMasking() const");
  for (const condition of [
    "StaticPrefs::cloakfox_enabled()",
    "StaticPrefs::cloakfox_sab_worker_timing_masking()",
    "!IsChromeWorker()",
    "!mIsPrivilegedAddonGlobal",
    "IsSharedMemoryAllowed()",
    "CrossOriginIsolated()",
  ]) {
    assert.ok(eligibility.includes(condition), `missing eligibility: ${condition}`);
  }

  const start = functionBody("void WorkerPrivate::StartCloakfoxTimingMasking()");
  const compact = start.replace(/\s+/g, " ");
  const load = compact.indexOf(
    "CloakfoxTiming::LoadKey(GetOriginAttributes().mUserContextId)");
  const reject = compact.indexOf("!key.IsValid()");
  const construct = compact.indexOf("MakeUnique<CloakfoxWorkerTiming::State>");
  assert.ok(load >= 0 && reject > load && construct > reject,
    "explicit-container key validation must precede state construction");
  assert.ok(start.includes("CloakfoxWorkerTiming::HashWorkerId"));
  assert.match(start,
    /if \(!ArmCloakfoxTimingTimer\([\s\S]*?NextInterruptDelayMs\(\)\)\) \{[\s\S]*?StopCloakfoxTimingMasking\(\);/);

  const doRunLoop = hunkContaining("InitializeGCTimers();");
  assert.ok(doRunLoop.indexOf("StartCloakfoxTimingMasking();") >
    doRunLoop.indexOf("InitializeGCTimers();"));
});

test("callback resolves the live worker and delegates only its boundary", () => {
  const callback = functionBody(
    "void WorkerPrivate::CloakfoxTimingTimerCallback");
  assert.ok(callback.includes("GetCurrentThreadWorkerPrivate()"));
  assert.ok(callback.includes("workerPrivate->RunCloakfoxTimingBoundary()"));
  assert.ok(!callback.includes("aClosure"), "callback must not dereference a raw closure");
});

test("every shutdown path closes the rearm gate before destruction", () => {
  const stop = functionBody("void WorkerPrivate::StopCloakfoxTimingMasking()");
  const deactivate = stop.indexOf("mCloakfoxTimingMaskingActive = false;");
  const cancel = stop.indexOf("mCloakfoxTimingTimer->Cancel()");
  const clearState = stop.indexOf("mCloakfoxTimingState = nullptr;");
  assert.ok(deactivate >= 0 && cancel > deactivate && clearState > cancel,
    "stop must deactivate before canceling and clearing state");

  const neverRan = hunkContaining("void WorkerPrivate::RunLoopNeverRan()");
  assert.ok(neverRan.includes("StopCloakfoxTimingMasking();"));

  const notify = hunkContaining(
    'NS_ASSERTION(aStatus > Running && aStatus < Dead, "Bad status!")');
  assert.ok(notify.includes("StopCloakfoxTimingMasking();"));

  const finalDead = hunkContaining("DisableMemoryReporter();");
  assert.ok(finalDead.indexOf("StopCloakfoxTimingMasking();") >
    finalDead.indexOf("DisableMemoryReporter();"));

  const destructor = hunkContaining("WorkerPrivate::~WorkerPrivate()");
  for (const invariant of [
    "MOZ_DIAGNOSTIC_ASSERT(!mCloakfoxTimingTimer)",
    "MOZ_DIAGNOSTIC_ASSERT(!mCloakfoxTimingState)",
    "MOZ_DIAGNOSTIC_ASSERT(!mCloakfoxTimingMaskingActive)",
  ]) assert.ok(destructor.includes(invariant), `missing destructor invariant ${invariant}`);
});

test("arm failures disable policy without callback-time key or pref work", () => {
  const arm = functionBody("bool WorkerPrivate::ArmCloakfoxTimingTimer");
  assert.ok(arm.includes("InitWithNamedFuncCallback("));
  assert.ok(arm.includes("return NS_SUCCEEDED("));
  assert.ok(!arm.includes("MOZ_ALWAYS_SUCCEEDS"));

  const boundary = functionBody("void WorkerPrivate::RunCloakfoxTimingBoundary()");
  assert.match(boundary,
    /if \(!ArmCloakfoxTimingTimer\([\s\S]*?NextInterruptDelayMs\(\)\)\) \{[\s\S]*?StopCloakfoxTimingMasking\(\);/);
  for (const forbidden of ["StaticPrefs::", "LoadKey(", "MakeUnique<", "new "]) {
    assert.ok(!boundary.includes(forbidden),
      `timer boundary must not perform callback-time ${forbidden}`);
  }
});

test("keyed timing state advances yield and cadence at every boundary", () => {
  assert.ok(!headerAdded.includes("mCloakfoxTimingInterruptDelayMs"));
  assert.ok(!headerAdded.includes("mCloakfoxTimingYieldDelayUs"));
  const start = functionBody("void WorkerPrivate::StartCloakfoxTimingMasking()");
  assert.equal((start.match(/NextInterruptDelayMs\(\)/g) || []).length, 1);
  assert.equal((start.match(/NextYieldUs\(\)/g) || []).length, 0);

  const boundary = functionBody("void WorkerPrivate::RunCloakfoxTimingBoundary()");
  const yieldDraw = boundary.indexOf("mCloakfoxTimingState->NextYieldUs()");
  const realize = boundary.indexOf("RealizeCloakfoxTimingDelay(delayUs)");
  const cadenceDraw = boundary.indexOf(
    "mCloakfoxTimingState->NextInterruptDelayMs()");
  assert.ok(yieldDraw >= 0 && realize > yieldDraw && cadenceDraw > realize,
    "each boundary must draw a yield, realize it, then draw the next cadence");
  assert.equal((boundary.match(/NextYieldUs\(\)/g) || []).length, 1);
  assert.equal((boundary.match(/NextInterruptDelayMs\(\)/g) || []).length, 1);
});
