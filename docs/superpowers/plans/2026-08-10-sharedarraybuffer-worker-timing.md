# SharedArrayBuffer Worker Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve shared-memory semantics while preventing ordinary content workers from exposing a repeatable host CPU-throughput fingerprint through `SharedArrayBuffer` counters.

**Architecture:** A cross-origin-isolated regression fixture measures real SAB, Atomics, and Wasm behavior before any implementation. A small native scheduling-state object derives bounded interrupt/yield timing from the session key created by the performance-timeline plan. `WorkerPrivate` installs the policy only for eligible content workers, using Firefox's worker control-event/interrupt path so tight JavaScript and Wasm loops reach safe scheduling boundaries without altering memory values.

**Tech Stack:** Firefox 146 worker runtime and SpiderMonkey interrupt callbacks, XPCOM timers, C++ `TimeDuration`, Python `ThreadingHTTPServer`, Selenium/geckodriver, WebAssembly shared memory.

## Global Constraints

- This plan depends on completed Task 1 and Task 2 of `docs/superpowers/plans/2026-08-10-performance-timeline-timing.md`, specifically the per-container session key and `CloakfoxTiming::LoadKey(uint32_t)`.
- Keep `SharedArrayBuffer`, shared typed arrays, all ordinary `Atomics` results, wait/notify, and Wasm shared memory functional.
- Never perturb shared-memory contents, atomic return values, or happens-before semantics.
- Do not patch page-visible `Atomics` methods and do not inject MAIN-world scripts.
- Exclude chrome workers, extension workers, audio worklets, and other real-time worklet threads.
- Gate the policy on `cloakfox.enabled`, cross-origin isolation/shared-memory eligibility, and `cloakfox.sab_worker_timing_masking`.
- The emergency pref starts disabled during development and becomes default-enabled only after correctness, masking, and performance acceptance gates pass.
- No injected yield may exceed 1 ms; enabled median slowdown must remain at or below 5% over at least 20 alternating samples.
- If masking cannot pass within the performance budget, leave the pref disabled and report the residual gap; do not increase delays silently.
- Modify source-of-truth files under `additions/` and `patches/`; generated `firefox-src/` edits are build artifacts only.
- Follow red-green-refactor and observe the enabled-vs-disabled probe fail before adding the worker policy.

---

## File structure

- Create `tests/fingerprint/probe_sharedarraybuffer_timing.py`: local COOP/COEP server, correctness checks, counter distributions, and performance gate.
- Create `tests/fingerprint/fixtures/sab-worker.js`: dedicated-worker correctness and counter workloads.
- Create `tests/fingerprint/fixtures/sab-shared-worker.js`: shared-worker workload.
- Create `tests/fingerprint/fixtures/sab-service-worker.js`: service-worker workload and controlled-client messaging.
- Create `tests/fingerprint/fixtures/sab-counter.wasm`: minimal module importing shared memory and atomically incrementing a counter in a bounded loop.
- Create `additions/cloakcfg/CloakfoxWorkerTiming.h`: policy eligibility-independent deterministic scheduling state.
- Create `additions/cloakcfg/CloakfoxWorkerTiming.cpp`: schedule generation and bounded-yield calculation.
- Modify `additions/cloakcfg/moz.build`: compile/export worker timing state.
- Create `patches/sab-worker-timing-masking.patch`: static pref plus `WorkerPrivate` timer/interrupt integration.
- Modify `patches/order.txt`: apply after `performance-timeline-timing.patch` and existing worker patches.
- Modify `settings/cloakfox.cfg`: document the emergency pref and fingerprint/security boundary.
- Modify `tests/fingerprint/README.md`, `docs/fingerprint-coverage.md`, and `docs/cpp-first/inventory.md`: record measured coverage and limitations.

## Task 1: Cross-origin-isolated SAB correctness and fingerprint fixture

**Files:**
- Create: `tests/fingerprint/probe_sharedarraybuffer_timing.py`
- Create: `tests/fingerprint/fixtures/sab-worker.js`
- Create: `tests/fingerprint/fixtures/sab-shared-worker.js`
- Create: `tests/fingerprint/fixtures/sab-service-worker.js`
- Create: `tests/fingerprint/fixtures/sab-counter.wasm`

**Interfaces:**
- Produces probe modes: `correctness`, `distribution`, and `performance`.
- Produces browser result fields: `crossOriginIsolated`, `sabType`, `atomics`, `dedicated`, `shared`, `service`, `wasm`, and `samples`.
- Consumes prefs: `cloakfox.enabled` and `cloakfox.sab_worker_timing_masking`.

- [ ] **Step 1: Add a real COOP/COEP test server**

Implement a `ThreadingHTTPServer` handler that serves every fixture with:

```python
self.send_header("Cross-Origin-Opener-Policy", "same-origin")
self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
self.send_header("Cross-Origin-Resource-Policy", "same-origin")
self.send_header("Cache-Control", "no-store")
```

Bind to `127.0.0.1` on port `0`, run the server in a daemon thread, and stop it
in `finally`. The page must first assert `crossOriginIsolated === true`,
`typeof SharedArrayBuffer === "function"`, and
`new WebAssembly.Memory({initial: 1, maximum: 1, shared: true}).buffer instanceof SharedArrayBuffer`.

- [ ] **Step 2: Add exact shared-memory correctness workloads**

The dedicated worker accepts `{mode, buffer, iterations}`. Its correctness path
runs exactly `iterations` calls to `Atomics.add(view, 0, 1)` and posts the final
value. A second worker blocks in `Atomics.wait(view, 1, 0, 5000)` while the page
stores `1` and calls `Atomics.notify`; assert the waiter reports `"ok"` and the
stored value remains `1`.

The shared and service worker fixtures perform the same bounded increment when
supported. Use explicit skip results for browser/platform absence; never turn a
missing optional worker kind into a false PASS.

Build `sab-counter.wasm` from this fixed source and commit the binary fixture:

```wat
(module
  (memory (import "env" "memory") 1 1 shared)
  (func (export "run") (param $count i32)
    (local $i i32)
    (loop $again
      (drop (i32.atomic.rmw.add (i32.const 0) (i32.const 1)))
      (local.set $i (i32.add (local.get $i) (i32.const 1)))
      (br_if $again (i32.lt_u (local.get $i) (local.get $count))))))
```

Generate it once with `wat2wasm --enable-threads`, serve it as
`application/wasm`, and assert after `run(N)` that the imported shared-memory
counter equals exactly `N`. Commit both the SHA-256 printed by
`shasum -a 256 tests/fingerprint/fixtures/sab-counter.wasm` in the probe comment
and the binary; the test must reject a fixture with a different digest.

- [ ] **Step 3: Add distribution and performance measurements**

For a counter-rate sample, run a worker increment loop while the page waits a
fixed 250 ms using its normal event loop, then signal stop and record the final
counter. Collect 24 samples after four warmups. For the bounded CPU benchmark,
time a fixed 5,000,000-iteration worker loop and collect 20 alternating enabled
and disabled samples in separate fresh profiles.

Calculate median, median absolute deviation, and coefficient of variation in
Python. Print raw samples and summary values so a failure is diagnosable.

- [ ] **Step 4: Add failing enabled-vs-disabled assertions**

Correctness mode requires exact values in both pref states. Distribution mode
requires all of the following:

```python
assert enabled["samples"] != disabled["samples"]
assert enabled["mad"] > disabled["mad"] * 1.25
assert abs(enabled["median"] - disabled["median"]) > disabled["mad"]
```

Performance mode requires:

```python
slowdown = enabled_median / disabled_median - 1.0
assert slowdown <= 0.05
```

Keep distribution thresholds named constants with comments explaining that
they are acceptance bounds, not universal statistical claims.

- [ ] **Step 5: Run correctness and verify baseline PASS**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness`

Expected: PASS, proving SAB/Atomics/Wasm work before the policy exists.

- [ ] **Step 6: Run distribution and verify RED**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution`

Expected: FAIL because the new pref has no implementation and enabled/disabled behavior is statistically indistinguishable.

- [ ] **Step 7: Commit the executable threat model**

```bash
git add tests/fingerprint/probe_sharedarraybuffer_timing.py \
  tests/fingerprint/fixtures/sab-worker.js \
  tests/fingerprint/fixtures/sab-shared-worker.js \
  tests/fingerprint/fixtures/sab-service-worker.js \
  tests/fingerprint/fixtures/sab-counter.wasm
git commit -m "test: measure shared-memory timing fingerprints"
```

## Task 2: Deterministic bounded worker timing state

**Files:**
- Create: `additions/cloakcfg/CloakfoxWorkerTiming.h`
- Create: `additions/cloakcfg/CloakfoxWorkerTiming.cpp`
- Modify: `additions/cloakcfg/moz.build`
- Create: `patches/sab-worker-timing-masking.patch`
- Modify: `patches/order.txt`

**Interfaces:**
- Consumes: `CloakfoxTiming::Key` and `CloakfoxTiming::LoadKey(uint32_t)`.
- Produces: `CloakfoxWorkerTiming::State(CloakfoxTiming::Key key, uint64_t streamId)`.
- Produces: `uint32_t NextInterruptDelayMs()` in inclusive range 3–9 ms.
- Produces: `uint32_t NextYieldUs()` in inclusive range 0–250 microseconds.
- Produces: `bool ShouldYield()` with a keyed 3-in-4 duty cycle.

- [ ] **Step 1: Add compile-time range tests before implementation**

Put the range constants in the header and enforce the design bounds:

```cpp
static constexpr uint32_t kMinInterruptMs = 3;
static constexpr uint32_t kMaxInterruptMs = 9;
static constexpr uint32_t kMaxYieldUs = 250;
static_assert(kMinInterruptMs > 0);
static_assert(kMinInterruptMs <= kMaxInterruptMs);
static_assert(kMaxYieldUs <= 1000);
```

Add declarations without definitions, add the source to `UNIFIED_SOURCES`, and
copy the three changed addition files into the generated tree before attempting
the build:

```bash
cp additions/cloakcfg/CloakfoxWorkerTiming.h \
  additions/cloakcfg/CloakfoxWorkerTiming.cpp additions/cloakcfg/moz.build \
  firefox-src/cloakcfg/
```

- [ ] **Step 2: Run the build and verify RED**

Run: `cd firefox-src && ./mach build`

Expected: link failure for the undefined `State` methods, confirming the new
compiled interface is exercised.

- [ ] **Step 3: Implement deterministic state transitions**

Use a nonzero xorshift128+ state initialized by mixing both key words with the
stable worker stream id. Implement ranges without allocation or wall-clock
input:

```cpp
uint32_t State::NextInterruptDelayMs() {
  return kMinInterruptMs + NextU32() %
         (kMaxInterruptMs - kMinInterruptMs + 1);
}

bool State::ShouldYield() { return (NextU32() & 3u) != 0; }

uint32_t State::NextYieldUs() {
  return ShouldYield() ? NextU32() % (kMaxYieldUs + 1) : 0;
}
```

Hash `WorkerPrivate::mId` UTF-16 code units into the stream id with a documented
FNV-1a loop. Do not use the pointer value. Two workers in one container must
receive different streams; the same worker retains one state object for its
entire lifetime.

- [ ] **Step 4: Add the emergency StaticPref disabled by default**

In `sab-worker-timing-masking.patch`, extend
`modules/libpref/init/StaticPrefList.yaml`:

```yaml
- name: cloakfox.sab_worker_timing_masking
  type: RelaxedAtomicBool
  value: false
  mirror: always
```

Append the patch after `performance-timeline-timing.patch` in
`patches/order.txt`.

- [ ] **Step 5: Build and verify GREEN**

Sync the completed helper, apply the integration patch, and build:

```bash
cp additions/cloakcfg/CloakfoxWorkerTiming.h \
  additions/cloakcfg/CloakfoxWorkerTiming.cpp additions/cloakcfg/moz.build \
  firefox-src/cloakcfg/
cd firefox-src
patch -p1 < ../patches/sab-worker-timing-masking.patch
./mach build
```

Expected: successful compile/link with the pref still disabled and no behavior change.

- [ ] **Step 6: Commit the scheduling state**

```bash
git add additions/cloakcfg/CloakfoxWorkerTiming.h \
  additions/cloakcfg/CloakfoxWorkerTiming.cpp additions/cloakcfg/moz.build \
  patches/sab-worker-timing-masking.patch patches/order.txt
git commit -m "feat: add bounded worker timing schedules"
```

## Task 3: Worker interrupt and safe-yield integration

**Files:**
- Modify: `patches/sab-worker-timing-masking.patch`

**Interfaces:**
- Consumes: `CloakfoxWorkerTiming::State` from Task 2.
- Produces on `WorkerPrivate`: `StartCloakfoxTimingMasking()`, `StopCloakfoxTimingMasking()`, and `RunCloakfoxTimingBoundary()`.
- Owns: one `nsITimer` and one timing state per eligible worker.

- [ ] **Step 1: Add a failing policy-activation assertion**

Run the distribution probe with the pref explicitly true in its generated
`user.js` and retain the RED result from Task 1. Also run correctness to retain
the known-green semantic baseline.

```bash
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness --masking on
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution --masking on
```

Expected: correctness PASS; distribution FAIL.

- [ ] **Step 2: Add strict worker eligibility**

In the `WorkerPrivate` patch, return false unless every condition holds:

```cpp
bool WorkerPrivate::ShouldUseCloakfoxTimingMasking() const {
  return StaticPrefs::cloakfox_enabled() &&
         StaticPrefs::cloakfox_sab_worker_timing_masking() &&
         !IsChromeWorker() && !mIsPrivilegedAddonGlobal &&
         IsSharedMemoryAllowed() && CrossOriginIsolated();
}
```

Ordinary dedicated, shared, and service workers are eligible. Worklet runtimes
do not use `WorkerPrivate` and therefore remain excluded. Do not infer
eligibility merely because the constructor named `SharedArrayBuffer` exists.
Mirror each new hunk into the already-patched generated `firefox-src/` files
with `apply_patch` before the next build; keep
`patches/sab-worker-timing-masking.patch` as the committed source of truth.

- [ ] **Step 3: Install a worker-control timer**

After the content `WorkerGlobalScope` is created and before user script runs,
load the explicit `GetOriginAttributes().mUserContextId` key, build the stream
id from `mId`, and create a one-shot `nsITimer` targeted at
`mWorkerControlEventTarget`.

The timer callback must:

```cpp
void WorkerPrivate::RunCloakfoxTimingBoundary() {
  AssertIsOnWorkerThread();
  if (!ShouldUseCloakfoxTimingMasking() || !mCloakfoxTimingState) return;
  const uint32_t delayUs = mCloakfoxTimingState->NextYieldUs();
  if (delayUs) {
    PR_Sleep(PR_MicrosecondsToInterval(delayUs));
  }
  ArmCloakfoxTimingTimer(mCloakfoxTimingState->NextInterruptDelayMs());
}
```

Dispatch through the worker control event target so Firefox requests a
SpiderMonkey interrupt when a long-running JavaScript or Wasm task prevents
normal event processing. Never sleep while holding `mMutex`; never allocate or
read preferences inside the timer callback. Cache eligibility and key material
before arming.

- [ ] **Step 4: Stop the timer on every shutdown path**

Cancel and clear the timer before `mStatus` becomes `Dead`, in
`RunLoopNeverRan()`, and in the destructor as a defensive assertion. The timer
must not retain a dead `WorkerPrivate` or rearm after cancellation.

- [ ] **Step 5: Build and run correctness GREEN**

```bash
cd firefox-src && ./mach build && cd ..
make relink
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness --masking on
```

Expected: exact shared-memory, Atomics wait/notify, and Wasm results all PASS.

- [ ] **Step 6: Run distribution GREEN**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution --masking on`

Expected: PASS the named distribution thresholds. If it fails, adjust only the
3–9 ms cadence or 0–250 µs yield distribution while retaining the 1 ms hard
cap, then rerun correctness before every distribution attempt.

- [ ] **Step 7: Commit the worker integration**

```bash
git add patches/sab-worker-timing-masking.patch
git commit -m "feat: mask shared-worker timing throughput"
```

## Task 4: Performance acceptance and default enablement

**Files:**
- Modify: `patches/sab-worker-timing-masking.patch`
- Modify: `settings/cloakfox.cfg`
- Modify: `tests/fingerprint/probe_sharedarraybuffer_timing.py`

**Interfaces:**
- Changes StaticPref default from false to true only if every gate passes.
- Documents `cloakfox.sab_worker_timing_masking` as an emergency rollback pref.

- [ ] **Step 1: Run the alternating performance gate**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode performance`

Expected: at least 20 enabled and 20 disabled samples, no outlier removal, and
enabled median slowdown at or below 5%.

- [ ] **Step 2: Run combined correctness and masking gates**

```bash
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness --masking on
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution --masking on
```

Expected: both PASS after the performance run, ruling out a one-off warm-cache result.

- [ ] **Step 3: Enable the pref only after all gates pass**

Change the StaticPref value to `true`. In `settings/cloakfox.cfg`, document:

```js
// Emergency rollback for SharedArrayBuffer worker-throughput masking.
// true preserves SAB/Atomics values but adds bounded scheduling variation to
// cross-origin-isolated content workers. Set false and restart if a worker-
// heavy application shows a regression.
defaultPref("cloakfox.sab_worker_timing_masking", true);
```

If any gate cannot pass inside the hard limits, keep the StaticPref and cfg
default `false`, add the measured result to the documentation, and do not label
the SAB vector covered.

Mirror the accepted StaticPref value into the generated
`firefox-src/modules/libpref/init/StaticPrefList.yaml` before rebuilding.

- [ ] **Step 4: Rebuild and test the actual default**

```bash
cd firefox-src && ./mach build && cd ..
make relink
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode performance
```

Expected: all three PASS without forcing the pref.

- [ ] **Step 5: Commit the accepted default**

```bash
git add patches/sab-worker-timing-masking.patch settings/cloakfox.cfg \
  tests/fingerprint/probe_sharedarraybuffer_timing.py
git commit -m "feat: enable bounded SAB timing masking"
```

Use `test: record SAB masking limits` instead if the safe default remains off.

## Task 5: Regression and documentation gate

**Files:**
- Modify: `tests/fingerprint/README.md`
- Modify: `docs/fingerprint-coverage.md`
- Modify: `docs/cpp-first/inventory.md`

**Interfaces:**
- Documents the measured result, eligible worker types, rollback pref, 5% budget, and real-time-worklet exclusion.

- [ ] **Step 1: Document the exact boundary**

Describe this as throughput-fingerprint masking, not universal elimination of
all SAB clocks or Spectre mitigation. Record whether the default was enabled,
the observed slowdown, the distribution statistics, and that audio/worklet
render threads are excluded to preserve real-time behavior.

- [ ] **Step 2: Verify patch hygiene and clean application**

```bash
git diff --check
node --test tests/fingerprint/test_*.mjs
python -m pytest --noconftest tests/fingerprint/test_*.py -q
```

Then, in the isolated execution worktree only:

```bash
make setup-minimal
make dir
find firefox-src -name '*.rej' -print -quit | grep -q . && exit 1 || true
```

Expected: all unit tests PASS, `make dir` exits 0, and no reject file exists.

- [ ] **Step 3: Run worker and kill-switch regressions**

```bash
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode correctness
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode distribution
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_sharedarraybuffer_timing.py --mode performance
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_worker_container.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_workers.py
CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/probe_enabled_killswitch.py
```

Expected: no exit 1. A documented platform-inconclusive exit 2 is acceptable
only for an optional worker kind; dedicated-worker SAB correctness must run.

- [ ] **Step 4: Run aggregate regression suite**

Run: `CLOAKFOX_BIN="$CLOAKFOX_BIN" python tests/fingerprint/run_all.py`

Expected: zero failed probes.

- [ ] **Step 5: Commit the measured coverage record**

```bash
git add tests/fingerprint/README.md docs/fingerprint-coverage.md \
  docs/cpp-first/inventory.md
git commit -m "docs: record shared-memory timing boundaries"
```

The implementation handoff must quote the exact correctness, distribution,
and slowdown results and state whether the default was enabled. Do not claim
the SAB gap closed if the pref remained off.
