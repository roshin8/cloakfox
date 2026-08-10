# Performance Timeline Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `performance.now()` and all eight Firefox 146 performance-entry types one native, coherent, per-container-session timing presentation without changing API availability or author-supplied User Timing values.

**Architecture:** `CloakfoxSeedSync` derives a two-word session timing key for every container and places it in that container's `MaskConfig` overlay. A focused native helper implements a pure monotonic transform, while `Performance` owns the resolved key and exposes presentation methods used by native timing getters. The existing actor continues callback scheduling jitter but stops replacing `Performance.prototype.now`.

**Tech Stack:** Firefox 146 C++/WebIDL internals, Mozilla `Maybe` and DOM performance classes, JSWindowActors, Node's built-in test runner, Python 3, Selenium/geckodriver.

## Global Constraints

- Keep `SharedArrayBuffer`, `Atomics`, `PerformanceObserver`, and all supported entry types available.
- Keep `privacy.reduceTimerPrecision` and both existing timer option prefs semantically unchanged.
- Preserve explicit author-provided `PerformanceMark`/`PerformanceMeasure` values bit-for-bit.
- Apply presentation only at content-facing boundaries; internal entry sorting, buffering, profiling, and duration-threshold logic use raw values.
- Preserve native descriptors and property placement; add no page-instance own properties.
- Gate every Cloakfox path on `cloakfox.enabled`; missing or invalid keys fall back to stock Firefox.
- Modify source-of-truth files under `additions/` and `patches/`; do not treat the generated `firefox-src/` tree as the committed source.
- Runtime probes use Selenium, not Playwright, and launch the binary named by `CLOAKFOX_BIN`.
- Follow red-green-refactor: observe each new runtime assertion failing before implementing its production change.

---

## File structure

- Create `additions/cloakcfg/CloakfoxTiming.h`: small public timing-key and transform interface.
- Create `additions/cloakcfg/CloakfoxTiming.cpp`: key loading and pure timestamp/interval transform.
- Modify `additions/cloakcfg/moz.build`: compile/export the helper in `xul`.
- Modify `additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs`: generate and install per-launch container timing keys.
- Modify `additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs`: retain timer/rAF jitter and remove the page `performance.now()` wrapper.
- Create `patches/performance-timeline-timing.patch`: integrate the helper with Gecko performance classes.
- Modify `patches/order.txt`: apply the new patch after worker container identity is available.
- Create `tests/fingerprint/test_timing_session_key.mjs`: unit-test the shipped JS key derivation and config merge.
- Create `tests/fingerprint/test_timing_ownership.mjs`: enforce that native Gecko, not the actor, owns `performance.now()` presentation.
- Create `tests/fingerprint/probe_performance_timeline.py`: exercise the native browser behavior and all advertised entry types.
- Modify `tests/fingerprint/probe_timing_jitter.py`: assert native clock behavior and cross-reload coherence.
- Modify `tests/fingerprint/probe_actor_stealth.py`: verify `performance.now` is native rather than actor-exported.
- Modify `tests/fingerprint/README.md`, `docs/fingerprint-coverage.md`, and `docs/cpp-first/inventory.md`: document ownership and coverage.

## Task 1: Per-container session timing key

**Files:**
- Modify: `additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs`
- Create: `tests/fingerprint/test_timing_session_key.mjs`

**Interfaces:**
- Produces: `deriveTimingSessionKey(seedB64: string, saltB64: string): { hi: number, lo: number }`
- Produces: `mergeSessionTimingKey(cfgJson: string, key: { hi: number, lo: number }): string`
- Produces config keys: `timing:session_key_hi` and `timing:session_key_lo`, both unsigned 32-bit integers.

- [ ] **Step 1: Write the failing key-derivation tests**

Extract the two exported pure functions from the real source using the brace-balancing pattern already used by `test_seedsync_fonts.mjs`. Add these assertions:

```js
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
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/fingerprint/test_timing_session_key.mjs`

Expected: FAIL because `deriveTimingSessionKey` and `mergeSessionTimingKey` are absent from the shipped module.

- [ ] **Step 3: Implement the pure derivation and merge**

Use all 32 seed bytes and 32 salt bytes. Keep the function synchronous because startup seed installation is synchronous:

```js
export function deriveTimingSessionKey(seedB64, saltB64) {
  const seed = atob(seedB64);
  const salt = atob(saltB64);
  if (seed.length !== 32 || salt.length !== 32) {
    throw new TypeError("timing seed and session salt must be 32 bytes");
  }
  let hi = 0x9e3779b9;
  let lo = 0x85ebca6b;
  for (let i = 0; i < 32; i++) {
    hi = Math.imul(hi ^ seed.charCodeAt(i), 16777619) >>> 0;
    lo = Math.imul(lo ^ salt.charCodeAt(i), 2246822507) >>> 0;
    hi = (hi ^ (lo >>> 13)) >>> 0;
    lo = (lo ^ (hi >>> 15)) >>> 0;
  }
  return { hi: hi || 1, lo: lo || 1 };
}

export function mergeSessionTimingKey(cfgJson, key) {
  let cfg = {};
  try {
    const parsed = JSON.parse(cfgJson || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) cfg = parsed;
  } catch (_e) {}
  return JSON.stringify({
    ...cfg,
    "timing:session_key_hi": key.hi >>> 0,
    "timing:session_key_lo": key.lo >>> 0,
  });
}
```

Create one module-scoped `SESSION_TIMING_SALT = randomSeedB64()`. After each call to `ensureContainerSeeds(ucid)` has created/repaired the persistent seeds and config, derive from `cloakfox.container.<ucid>.timing_seed`, merge into `cloakfox.s.cloak_cfg_<ucid>`, and write only when the JSON string changed. Existing persona/override keys must win everywhere except the two internal session-key fields, which are always replaced at startup.

- [ ] **Step 4: Run unit tests and verify GREEN**

Run: `node --test tests/fingerprint/test_timing_session_key.mjs tests/fingerprint/test_seedsync_fonts.mjs`

Expected: all tests PASS with no warnings.

- [ ] **Step 5: Commit the session-key unit**

```bash
git add additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs \
  tests/fingerprint/test_timing_session_key.mjs
git commit -m "feat: derive per-session timing keys"
```

## Task 2: Native transform and `performance.now()`

**Files:**
- Create: `additions/cloakcfg/CloakfoxTiming.h`
- Create: `additions/cloakcfg/CloakfoxTiming.cpp`
- Modify: `additions/cloakcfg/moz.build`
- Create: `patches/performance-timeline-timing.patch`
- Modify: `patches/order.txt`
- Modify: `tests/fingerprint/probe_timing_jitter.py`

**Interfaces:**
- Produces: `CloakfoxTiming::Key { uint32_t mHi; uint32_t mLo; bool IsValid() const; }`
- Produces: `CloakfoxTiming::Interval { double mStart; double mEnd; double Duration() const; }`
- Produces: `Key LoadKey(uint32_t userContextId)`
- Produces: `double TransformTimestamp(double raw, const Key& key, uint64_t streamId = 0)`
- Produces: `Interval TransformInterval(double start, double end, const Key& key, uint64_t streamId = 0)`
- Produces on `Performance`: `PresentTimestamp`, `PresentInterval`, and `HasCloakfoxTimingKey`.

- [ ] **Step 1: Extend the runtime probe with failing native-path assertions**

In `probe_timing_jitter.py`, collect two same-profile page loads plus samples
from a dedicated worker and return:

```js
const proto = Object.getOwnPropertyDescriptor(Performance.prototype, "now");
const own = Object.getOwnPropertyDescriptor(performance, "now");
return {
  samples: Array.from({length: 4000}, () => performance.now()),
  ownNow: !!own,
  nativeNow: !!proto && Function.prototype.toString.call(proto.value)
                    .includes("[native code]"),
  workerSamples: await new Promise((resolve, reject) => {
    const src = `postMessage(Array.from({length: 256}, () => performance.now()))`;
    const worker = new Worker(URL.createObjectURL(
      new Blob([src], {type: "text/javascript"})));
    worker.onmessage = event => resolve(event.data);
    worker.onerror = reject;
  }),
};
```

Assert no decreasing samples, at least one fractional sample, no own property,
native function stringification, the same interpolation for integer buckets
observed on both reloads in the same browser session, and fractional monotonic
worker samples.

- [ ] **Step 2: Run the probe and verify RED**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_timing_jitter.py`

Expected: FAIL because dedicated-worker `performance.now()` bypasses the window
actor and exposes Firefox's underlying quantized readings.

- [ ] **Step 3: Add the focused native helper**

Declare the helper without DOM dependencies in `CloakfoxTiming.h`. Implement the monotonic mapping in `CloakfoxTiming.cpp`:

```cpp
double TransformTimestamp(double aRaw, const Key& aKey, uint64_t aStreamId) {
  if (!aKey.IsValid() || !std::isfinite(aRaw) || aRaw < 0) return aRaw;
  const uint64_t bucket = static_cast<uint64_t>(std::floor(aRaw));
  const double fraction = aRaw - double(bucket);
  const double left = UnitJitter(bucket, aKey, aStreamId);
  const double right = UnitJitter(bucket + 1, aKey, aStreamId);
  const double offset = left + (right - left) * fraction;
  return aRaw + 0.999 * offset;
}

Interval TransformInterval(double aStart, double aEnd, const Key& aKey,
                           uint64_t aStreamId) {
  const double start = TransformTimestamp(aStart, aKey, aStreamId);
  const double end = TransformTimestamp(std::max(aStart, aEnd), aKey, aStreamId);
  return {start, std::max(start, end)};
}
```

`UnitJitter` maps the SplitMix64 output to `[0, 1)`. Linear interpolation makes
the offset continuous at millisecond boundaries; because its amplitude is
`0.999`, the transform's slope remains positive even for the largest possible
drop between adjacent keyed offsets. This preserves monotonicity without
call-order state or flattening real sub-millisecond input when
`timer_quantization_off` is enabled. Never use `rand()`, wall time, object
addresses, or call order. `LoadKey` reads the two unsigned `MaskConfig` fields
for the explicit container id and returns an invalid key if either is missing.

Add `CloakfoxTiming.cpp` to `UNIFIED_SOURCES` and both headers to `EXPORTS` in `additions/cloakcfg/moz.build`.

- [ ] **Step 4: Integrate the helper with `Performance::Now()`**

In `patches/performance-timeline-timing.patch`, modify
`modules/libpref/init/StaticPrefList.yaml` to declare
`cloakfox.opt.timer_high_precision_jitter` as a `RelaxedAtomicBool` with value
`true` and `mirror: always`. This makes the existing option safe to read from
window and worker performance objects without an off-main-thread pref lookup.

Modify `dom/performance/Performance.h` and `.cpp` so the constructor resolves `userContextId` from `aGlobal->PrincipalOrNull()->OriginAttributesRef()` and caches `CloakfoxTiming::Key`. Add:

```cpp
DOMHighResTimeStamp PresentTimestamp(DOMHighResTimeStamp aRaw,
                                     uint64_t aStreamId = 0) const;
CloakfoxTiming::Interval PresentInterval(DOMHighResTimeStamp aStart,
                                         DOMHighResTimeStamp aEnd,
                                         uint64_t aStreamId = 0) const;
bool HasCloakfoxTimingKey() const;
```

`PresentTimestamp` returns `aRaw` for the system principal, invalid key,
`cloakfox.enabled=false`, or
`StaticPrefs::cloakfox_opt_timer_high_precision_jitter()==false`.
Otherwise it calls the helper. `Performance::Now()` first performs Firefox's
existing precision reduction exactly once, then presents that reduced value.
`NowUnclamped()` remains raw for profiler/internal use.

Append `performance-timeline-timing.patch` to `patches/order.txt` after
`worker-container-identity.patch`, because worker `MaskConfig` reads depend on
that cache and explicit-container fix.

- [ ] **Step 5: Apply, build, and verify GREEN**

Apply the new patch to the generated tree, rebuild, and deploy the relinked XUL:

```bash
cp additions/cloakcfg/CloakfoxTiming.h additions/cloakcfg/CloakfoxTiming.cpp \
  additions/cloakcfg/moz.build firefox-src/cloakcfg/
cd firefox-src
patch -p1 < ../patches/performance-timeline-timing.patch
./mach build
cd ..
make relink
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_timing_jitter.py
```

Expected: build succeeds and the probe passes monotonicity, fractional output,
session reload coherence, and native identity.

- [ ] **Step 6: Commit the native clock unit**

```bash
git add additions/cloakcfg/CloakfoxTiming.h additions/cloakcfg/CloakfoxTiming.cpp \
  additions/cloakcfg/moz.build patches/performance-timeline-timing.patch \
  patches/order.txt tests/fingerprint/probe_timing_jitter.py
git commit -m "feat: move timing presentation into Gecko"
```

## Task 3: Performance timeline coverage

**Files:**
- Create: `tests/fingerprint/probe_performance_timeline.py`
- Modify: `patches/performance-timeline-timing.patch`

**Interfaces:**
- Consumes: `Performance::PresentTimestamp` and `Performance::PresentInterval` from Task 2.
- Produces: public timing consistency for all advertised performance entry types and their subtype fields.

- [ ] **Step 1: Write the all-entry runtime probe**

Serve a same-origin HTML page and resources from `ThreadingHTTPServer`. The page installs observers before loading an image/resource, creates default and explicit marks/measures, dispatches a real pointer event, and records navigation/paint/LCP entries after two animation frames. Store serialized results on `document.documentElement.dataset.cfxTimeline` so Selenium reads page-main-world values.

For every entry, capture:

```js
function snapshot(entry) {
  const extra = {};
  for (const key of [
    "processingStart", "processingEnd", "renderTime", "loadTime",
    "workerStart", "redirectStart", "redirectEnd", "fetchStart",
    "domainLookupStart", "domainLookupEnd", "connectStart", "connectEnd",
    "secureConnectionStart", "requestStart", "responseStart", "responseEnd"
  ]) if (key in entry) extra[key] = entry[key];
  return {
    name: entry.name, type: entry.entryType,
    startTime: entry.startTime, duration: entry.duration,
    rereadStart: entry.startTime, json: entry.toJSON(), extra,
  };
}
```

Assert:

- `PerformanceObserver.supportedEntryTypes` is unchanged and contains the eight types enabled by Firefox prefs;
- repeated reads and `toJSON()` match direct getters;
- every finite native-generated timestamp is nonnegative;
- resource/navigation phase fields are nondecreasing after ignoring spec-defined zero/unavailable fields;
- `duration >= 0` and equals the transformed endpoint difference where endpoints exist;
- observer and `performance.getEntries*()` snapshots match for the same entry;
- `performance.mark("explicit", {startTime: 123.25}).startTime === 123.25`;
- `performance.measure("explicit-measure", {start: 10.25, end: 20.75})` remains `startTime === 10.25` and `duration === 10.5`;
- default marks use the native presented clock;
- unsupported feature-gated types are reported as skips rather than failures.

- [ ] **Step 2: Run the new probe and verify RED**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_performance_timeline.py`

Expected: FAIL because native entry timestamps do not yet use the Cloakfox presentation helper and can disagree with `performance.now()`'s keyed fractional mapping.

- [ ] **Step 3: Patch common and subtype getters**

Extend `performance-timeline-timing.patch` across these Firefox files:

```text
dom/performance/PerformanceEntry.h
dom/performance/PerformanceEventTiming.{h,cpp}
dom/performance/PerformancePaintTiming.cpp
dom/performance/LargestContentfulPaint.{h,cpp}
dom/performance/PerformanceTiming.{h,cpp}
dom/performance/PerformanceResourceTiming.{h,cpp}
dom/performance/PerformanceNavigationTiming.{h,cpp}
```

Apply the same hunks to the already-patched files under `firefox-src/` with
`apply_patch` before rebuilding. The committed artifact remains
`patches/performance-timeline-timing.patch`; the mirrored generated-tree edits
exist only to execute the RED/GREEN cycle without resetting the build.

Use each entry's owning `Performance*`. Cache transformed endpoints in the
entry, then derive duration from those endpoints. Never independently jitter a
duration. TAO/CORS-protected zeros stay exactly zero. Event duration-threshold
checks and entry ordering continue to call raw accessors.

Do not re-transform User Timing objects. Default marks already store
`Performance::Now()` and therefore carry the presented clock; explicit marks
store the supplied value. Measures are constructed from the already resolved
mark/number/clock endpoints, preserving both cases without provenance flags.

- [ ] **Step 4: Build and verify the focused probe GREEN**

Run:

```bash
cd firefox-src && ./mach build && cd ..
make relink
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_performance_timeline.py
```

Expected: PASS for every advertised type, with explicit User Timing exact and all endpoint invariants satisfied.

- [ ] **Step 5: Commit complete entry coverage**

```bash
git add patches/performance-timeline-timing.patch \
  tests/fingerprint/probe_performance_timeline.py
git commit -m "feat: sanitize performance timeline entries"
```

## Task 4: Remove the actor clock and enforce stealth/coherence

**Files:**
- Modify: `additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs`
- Create: `tests/fingerprint/test_timing_ownership.mjs`
- Modify: `tests/fingerprint/probe_actor_stealth.py`
- Modify: `tests/fingerprint/probe_actors.py`

**Interfaces:**
- Consumes: native `Performance::Now()` presentation from Task 2.
- Preserves: actor wrapping of `setTimeout`, `setInterval`, and `requestAnimationFrame`.

- [ ] **Step 1: Write the failing ownership test and tighten stealth checks**

Read the real actor and patch sources and assert ownership structurally:

```js
test("Gecko owns performance.now timing presentation", () => {
  assert.ok(performancePatch.includes("Performance::Now()"));
  assert.ok(performancePatch.includes("PresentTimestamp"));
  assert.ok(!timingActor.includes("origPerfNow"));
  assert.ok(!timingActor.includes("Performance.prototype"));
});
```

Replace the actor-oriented `performance.now` expectation with these checks:

```js
const nowDescriptor = Object.getOwnPropertyDescriptor(Performance.prototype, "now");
r.performance_now = {
  instanceOwn: Object.hasOwn(performance, "now"),
  protoName: nowDescriptor.value.name,
  protoLength: nowDescriptor.value.length,
  nativeText: Function.prototype.toString.call(nowDescriptor.value),
};
```

Require `instanceOwn === false`, name `"now"`, length `0`, and native text. Keep the existing timer actor checks to prove the actor still installed its remaining wrappers.

- [ ] **Step 2: Run stealth tests and verify RED**

Run:

```bash
node --test tests/fingerprint/test_timing_ownership.mjs
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_actor_stealth.py
```

Expected: the Node ownership test FAILS on `origPerfNow`; the runtime stealth
probe remains green, demonstrating why descriptor checks alone cannot prove
which native-looking layer owns the method.

- [ ] **Step 3: Remove only the `performance.now()` actor block**

Delete the `cloakfox.opt.timer_high_precision_jitter` block from
`CloakfoxTimingChild.sys.mjs`, including the salt/hash implementation and
`Object.defineProperty(pageWin.Performance.prototype, "now", ...)`. Retain the
shared PRNG used by timeout, interval, and rAF wrappers.

Update the actor file header so it claims event-loop callback and rAF coverage,
not ownership of the performance clock. Update `probe_actors.py` comments to
identify native timing presentation.

- [ ] **Step 4: Deploy the loose actor and verify GREEN**

Copy the edited actor to both loose development locations described in
`CLAUDE.md`, then run:

```bash
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_actor_stealth.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_actors.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_performance_timeline.py
node --test tests/fingerprint/test_timing_ownership.mjs
```

Expected: all three probes PASS; timer/rAF actor behavior remains live while `performance.now` is native.

- [ ] **Step 5: Commit the ownership migration**

```bash
git add additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs \
  tests/fingerprint/test_timing_ownership.mjs \
  tests/fingerprint/probe_actor_stealth.py tests/fingerprint/probe_actors.py
git commit -m "refactor: retire the actor performance clock"
```

## Task 5: Regression gate and documentation

**Files:**
- Modify: `tests/fingerprint/README.md`
- Modify: `docs/fingerprint-coverage.md`
- Modify: `docs/cpp-first/inventory.md`

**Interfaces:**
- Documents: native performance timeline ownership, actor callback jitter, eight entry types, session stability, and explicit User Timing compatibility.

- [ ] **Step 1: Update the coverage documents**

State explicitly that Gecko owns `performance.now()` and performance-entry
presentation, while `CloakfoxTimingChild` owns timeout/interval/rAF callback
jitter. List all eight entry types and the additional fields covered. Document
that keys are stable only for one browser session and vary between containers.

- [ ] **Step 2: Run source and unit verification**

```bash
git diff --check
node --test tests/fingerprint/test_*.mjs
python -m pytest --noconftest tests/fingerprint/test_*.py -q
```

Expected: no whitespace errors and all unit tests PASS.

In the isolated execution worktree, verify the source-of-truth patch stack from
a clean generated tree:

```bash
make setup-minimal
make dir
find firefox-src -name '*.rej' -print -quit | grep -q . && exit 1 || true
```

Expected: `make dir` exits 0 and no reject file is printed. Do not run this
clean-tree check in a checkout containing an uncommitted generated Firefox
tree, because `setup-minimal` intentionally replaces `firefox-src/`.

- [ ] **Step 3: Run the focused browser regression set**

```bash
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_timing_jitter.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_performance_timeline.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_actor_stealth.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_worker_container.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_enabled_killswitch.py
```

Expected: every probe PASS or return documented platform-inconclusive exit 2; no exit 1.

- [ ] **Step 4: Run the aggregate probe suite**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/run_all.py`

Expected: zero failed probes.

- [ ] **Step 5: Commit documentation and final verification record**

```bash
git add tests/fingerprint/README.md docs/fingerprint-coverage.md \
  docs/cpp-first/inventory.md
git commit -m "docs: record native performance timing coverage"
```

Record the exact build binary path and focused/aggregate results in the commit
message body or implementation handoff; do not claim full SAB coverage from
this plan.
