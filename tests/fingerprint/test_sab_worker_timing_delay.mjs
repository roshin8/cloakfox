/* Regression gate for Darwin's 1 kHz NSPR interval conversion.
 *
 * PR_MicrosecondsToInterval(1..250) collapses to zero on that platform, so
 * PR_Sleep only yields instead of realizing the keyed sub-millisecond delay.
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

function functionBody(source, signature) {
  const start = source.indexOf(signature);
  assert.notEqual(start, -1, `missing ${signature}`);
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}" && --depth === 0) return source.slice(open + 1, i);
  }
  assert.fail(`unterminated ${signature}`);
}

function assertHighResolutionDelay(body) {
  assert.ok(body.includes("TimeDuration::FromMicroseconds(aDelayUs)"));
  assert.match(body, /const TimeStamp deadline\s*=\s*TimeStamp::Now\(\)\s*\+/);
  assert.match(body, /while \(TimeStamp::Now\(\) < deadline\)/);
  assert.ok(!body.includes("PR_Sleep("));
  assert.ok(!body.includes("PR_MicrosecondsToInterval("));
}

test("bounded worker delay uses a non-collapsing monotonic deadline", () => {
  const delay = functionBody(
    added, "void WorkerPrivate::RealizeCloakfoxTimingDelay");
  assertHighResolutionDelay(delay);

  const boundary = functionBody(
    added, "void WorkerPrivate::RunCloakfoxTimingBoundary()");
  assert.ok(boundary.includes(
    "RealizeCloakfoxTimingDelay(mCloakfoxTimingYieldDelayUs)"));
});

test("the regression gate rejects the old zero-interval NSPR implementation", () => {
  assert.throws(() => assertHighResolutionDelay(
    "PR_Sleep(PR_MicrosecondsToInterval(aDelayUs));"), assert.AssertionError);
  for (const delayUs of [1, 125, 250]) {
    assert.equal(Math.floor(delayUs * 1000 / 1_000_000), 0,
      "1 kHz NSPR conversion should reproduce the collapsed old interval");
  }
});
