/* Structural regression gate for the WorkerPrivate timing-mask lifecycle.
 *
 *   node --test tests/fingerprint/test_sab_worker_timing_lifecycle.mjs
 *
 * A full Gecko build proves type and linkage compatibility, but it cannot
 * prove that every shutdown route disables a queued timer before WorkerPrivate
 * dies. This gate checks the source-of-truth patch's ownership contract: one
 * worker-owned timer/state, worker-thread start, shutdown cancellation, and a
 * callback without a raw WorkerPrivate closure.
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
const added = patch.split("\n")
  .filter(line => line.startsWith("+") && !line.startsWith("+++"))
  .map(line => line.slice(1))
  .join("\n");

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

test("eligible workers cache one timing state before the run loop", () => {
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
  const compactStart = start.replace(/\s+/g, " ");
  const load = compactStart.indexOf(
    "CloakfoxTiming::LoadKey(GetOriginAttributes().mUserContextId)");
  const reject = compactStart.indexOf("!key.IsValid()");
  const construct = compactStart.indexOf("MakeUnique<CloakfoxWorkerTiming::State>");
  assert.ok(load >= 0 && reject > load && construct > reject,
    "the explicit-container key must be loaded and validated before state construction");
  assert.ok(start.includes("CloakfoxWorkerTiming::HashWorkerId"));
  assert.ok(start.includes(
    "ArmCloakfoxTimingTimer(mCloakfoxTimingState->NextInterruptDelayMs())"));

  assert.ok(added.includes("StartCloakfoxTimingMasking();"));
});

test("shutdown disables rearm and leaves no raw callback closure", () => {
  const stop = functionBody("void WorkerPrivate::StopCloakfoxTimingMasking()");
  const deactivate = stop.indexOf("mCloakfoxTimingMaskingActive = false;");
  const cancel = stop.indexOf("mCloakfoxTimingTimer->Cancel()");
  const clearState = stop.indexOf("mCloakfoxTimingState = nullptr;");
  assert.ok(deactivate >= 0 && cancel > deactivate && clearState > cancel,
    "stop must close the rearm gate before canceling and clearing state");

  const boundary = functionBody("void WorkerPrivate::RunCloakfoxTimingBoundary()");
  assert.ok(boundary.includes("if (!mCloakfoxTimingMaskingActive ||"));
  assert.ok(boundary.includes("mCloakfoxTimingState->NextYieldUs()"));
  assert.ok(boundary.includes(
    "PR_Sleep(PR_MicrosecondsToInterval(delayUs))"));
  assert.ok(boundary.includes("ArmCloakfoxTimingTimer("));
  for (const forbidden of ["StaticPrefs::", "LoadKey(", "MakeUnique<", "new "]) {
    assert.ok(!boundary.includes(forbidden),
      `timer boundary must not perform callback-time ${forbidden}`);
  }

  assert.match(added, /InitWithNamedFuncCallback\([\s\S]*?nullptr,[\s\S]*?TYPE_ONE_SHOT/);
  assert.ok((added.match(/StopCloakfoxTimingMasking\(\);/g) || []).length >= 3,
    "never-ran, shutdown notification, and final run-loop exit must all stop masking");
  assert.ok(added.includes("MOZ_DIAGNOSTIC_ASSERT(!mCloakfoxTimingTimer)"));
});
