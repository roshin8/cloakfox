/* Ownership regression test for the performance clock.
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

test("Gecko owns performance.now timing presentation", () => {
  assert.ok(performancePatch.includes("Performance::Now()"));
  assert.ok(performancePatch.includes("PresentTimestamp"));
  assert.ok(!timingActor.includes("origPerfNow"));
  assert.ok(!timingActor.includes("Performance.prototype"));
});
