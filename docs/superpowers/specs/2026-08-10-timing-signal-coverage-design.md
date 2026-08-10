# Timing Signal Coverage Design

**Date:** 2026-08-10
**Status:** Approved for implementation planning

## Summary

Cloakfox currently perturbs `performance.now()`, timers, and animation-frame
timestamps in `CloakfoxTimingChild`, but two timing surfaces remain outside that
model:

1. `PerformanceObserver` and the corresponding `PerformanceEntry` objects
   expose native timestamps that can contradict the actor's clock.
2. `SharedArrayBuffer` lets cooperating agents build a clock from shared-memory
   progress, bypassing timestamp APIs entirely.

The implementation must preserve these web-platform APIs. Cloakfox spoofs
fingerprintable signals; it does not remove capabilities as a shortcut. The
design therefore centralizes performance timestamp presentation in Gecko and
adds conservative execution-time variation to ordinary workers without
changing shared-memory contents or synchronization results.

The `SharedArrayBuffer` work targets stable CPU-throughput and timing
fingerprints. It does not claim to make every shared-memory clock unusable for
security research: unrestricted shared memory and strict semantic compatibility
make that guarantee infeasible without severe performance or behavior changes.

## Goals

- Keep `SharedArrayBuffer`, shared typed arrays, `Atomics`, and Wasm shared
  memory functional.
- Keep all supported `PerformanceObserver` entry types available:
  `event`, `first-input`, `largest-contentful-paint`, `mark`, `measure`,
  `navigation`, `paint`, and `resource`.
- Present one coherent, seeded, monotonic clock through `performance.now()`,
  performance entries, observer delivery, `getEntries*()`, and `toJSON()`.
- Make native-generated timing output stable when reread and internally
  consistent, while varying its fingerprint between Cloakfox identities.
- Preserve author-provided User Timing values exactly.
- Preserve native property placement, descriptors, function identity shape,
  and the global `cloakfox.enabled` kill switch.
- Avoid mutating application data or changing atomic-operation results.
- Bound the worker performance cost with an explicit regression test.

## Non-goals

- Hiding or disabling `SharedArrayBuffer`, `Atomics`, `PerformanceObserver`, or
  individual performance entry types.
- Claiming Spectre-class isolation from pages that retain unrestricted shared
  memory.
- Perturbing audio worklet render threads, whose real-time deadline makes
  injected stalls incompatible with glitch-free audio.
- Refactoring unrelated fingerprint patches or changing persona generation.
- Adding MAIN-world extension injection.

## Rejected approaches

### Page-side wrappers only

Extending `CloakfoxTimingChild` to wrap observer callbacks or performance-entry
prototypes would be quick, but it would not cover worker globals reliably and
would create more detectable page-object modifications. Wrapping observer lists
or entries with proxies would also change identity and brand behavior.

### Patching visible `Atomics` functions

This misses ordinary shared typed-array loads/stores, worker globals, optimized
JIT paths, and Wasm atomics. It is bypassable and therefore not an acceptable
boundary.

### Perturbing shared-memory values

Changing loads, stores, or atomic return values would corrupt application state
and violate synchronization semantics. Cloakfox must never use application data
as the noise carrier.

## Architecture

### Native timing presentation helper

Add a small Gecko-side Cloakfox timing helper owned by each content
`Performance` instance. At browser startup, `CloakfoxSeedSync` combines the
container's persisted `timing_seed` with one nonpersisted browser-session salt
and publishes the derived session timing key through the per-container
`MaskConfig` overlay. The helper resolves the current `userContextId` and reads
that key. The key remains stable for the life of the browser session and
differs across container identities. Workers resolve the same identity from
their `WorkerPrivate` origin attributes rather than assuming a browsing
context.

The helper exposes two presentation operations:

- `TransformTimestamp(raw, discriminator)` maps a nonnegative raw timestamp to
  a deterministic, monotonic presented timestamp.
- `TransformInterval(start, end, discriminator)` transforms both endpoints and
  returns coherent presented endpoints and a nonnegative duration.

The transform uses quantized raw time plus keyed fractional jitter. Its exact
PRF is an implementation detail, but it must satisfy these invariants:

- the same raw value and discriminator return the same presented value;
- increasing raw timestamps never produce decreasing presented timestamps;
- independently transformed fields that represent the same instant agree;
- intervals remain ordered and durations equal the difference of their
  presented endpoints;
- output is not reproducible with Cloakfox's former public, unsalted hash.

The discriminator distinguishes timelines or entry identities without making
repeated property reads vary. It must be based on stable entry data, not object
addresses or read order.

System-principal callers and code running while `cloakfox.enabled` is false use
Firefox's unmodified path.

### `performance.now()` integration

Move Cloakfox's `performance.now()` fractional-jitter behavior from the
JSWindowActor into the native helper. Keep the actor's `setTimeout`,
`setInterval`, and `requestAnimationFrame` behavior, but remove its
`Performance.prototype.now` replacement once native coverage exists. This
prevents double transformation and makes window and worker performance clocks
share the same presentation policy.

Firefox's underlying `privacy.reduceTimerPrecision` posture remains unchanged.
The existing `cloakfox.opt.timer_high_precision_jitter` and
`cloakfox.opt.timer_quantization_off` controls retain their documented meaning.

### Performance entry coverage

Apply the helper at the public getter boundary, after Firefox has computed the
real entry and before its timestamp reaches content. Internal scheduling,
sorting, buffering, and observer duration-threshold decisions continue using
raw values.

Coverage includes:

- base `PerformanceEntry.startTime` and `duration`;
- Event Timing `processingStart`, `processingEnd`, `startTime`, and `duration`;
- Largest Contentful Paint `renderTime`, `loadTime`, and `startTime`;
- navigation and resource phase timestamps, including worker, redirect, fetch,
  DNS, connection, secure-connection, request, and response milestones;
- paint timing timestamps;
- User Timing marks and measures created from native clock readings.

An entry caches its presented values so direct reads, observer reads,
`getEntries*()`, and `toJSON()` agree. Fields that refer to the same milestone
reuse the same transformed endpoint.

User-supplied values are data, not measured signals. An explicit mark
`startTime`, and measure endpoints or durations derived exclusively from
explicit author values, remain bit-for-bit unchanged. User Timing values that
default to the live clock use the transformed clock and remain coherent with
`performance.now()`.

### Shared-memory execution variation

Do not touch shared buffers or atomic results. Instead, add a narrowly scoped
worker-runtime policy for cross-origin-isolated content workers where shared
memory is available. At existing safe interrupt or scheduling boundaries, the
runtime occasionally yields for a small duration selected from a keyed,
bounded sequence derived from the container's session timing key.

This policy applies to ordinary dedicated, shared, and service workers and must
cover JavaScript and Wasm execution through the common runtime scheduling
boundary. It must not add a delay to every atomic operation, allocate on hot
paths, or depend on a worker voluntarily calling an API.

The sequence must be deterministic within the worker's container session but
must not repeat as a short obvious cycle. Its purpose is to make shared-counter
throughput and cross-thread progress an identity-shaped signal rather than a
stable measurement of the host CPU. Different workers receive derived streams
so they do not pause in lockstep.

Audio worklets and other real-time render threads are excluded. Their deadline
requirements make injected scheduling stalls unsafe. This limitation is
documented and covered by a regression test that verifies Cloakfox does not
degrade audio-worklet scheduling.

The worker policy is gated by `cloakfox.enabled` and a dedicated internal pref
for emergency rollback. It is enabled by default only after the runtime probes
meet both the masking and performance thresholds defined below.

## Compatibility and failure behavior

- Failure to resolve a seed falls back to Firefox's native behavior; it never
  exposes chrome errors to content.
- Timing output remains finite, nonnegative where required, and monotonic.
- Observer buffering and callback delivery are not delayed or reordered by the
  presentation transform.
- Shared-memory reads, writes, compare/exchange, wait/notify, and Wasm atomics
  retain their specified values and happens-before behavior.
- Worker execution variation is bounded and yields rather than busy-waits.
- The kill switch restores stock Firefox behavior after restart and leaves no
  own properties on page instances.

## Testing strategy

Implementation follows red-green-refactor. Runtime tests use Selenium and the
built Cloakfox binary, consistent with `tests/fingerprint/README.md`.

### Performance timeline probe

Add a probe that exercises every supported entry type available in the build
and verifies:

- all eight advertised types remain advertised;
- observer callbacks, `getEntries*()`, direct reads, and `toJSON()` agree;
- repeated reads are stable;
- timestamps are monotonic and intervals are coherent;
- native-generated values carry keyed fractional presentation;
- explicit User Timing values remain exact;
- the same container remains stable across reloads during a session;
- different containers produce different timing identities;
- disabling Cloakfox restores the native path;
- no own-property or descriptor regression exposes the implementation.

The probe must generate real resource, paint, event, navigation, mark, and
measure entries. Feature-gated entry types such as LCP are asserted when they
appear in `supportedEntryTypes`; absence caused by an upstream Firefox pref is
reported separately rather than confused with a Cloakfox failure.

### Shared-memory probe

Add a cross-origin-isolated test page and response headers so SAB is genuinely
available. Exercise:

- shared typed-array data exchange;
- the full ordinary `Atomics` synchronization path, including wait/notify;
- a Wasm shared-memory counter;
- dedicated, shared, and service worker execution where supported;
- repeated counter-rate measurements across worker streams and containers;
- the `cloakfox.enabled` and emergency-pref fallbacks.

Correctness assertions compare exact shared-memory values. Masking assertions
operate on distributions: a container's keyed scheduling profile must affect
counter-rate samples, and two independently keyed containers must not collapse
to the same repeatable host profile.

### Performance guardrail

Measure a fixed worker CPU task with the policy enabled and disabled on the
same build. The initial acceptance bound is no more than 5% median slowdown
over at least 20 alternating samples, with no individual injected yield longer
than 1 ms. If the masking requirement cannot be met inside that budget, the
worker policy remains behind its rollback pref and the implementation must
report the residual SAB gap rather than silently increasing the delay.

### Existing regressions

Run the timing jitter, actor stealth, worker-container, enabled-killswitch, and
aggregate fingerprint probe suites. Update the timing-jitter probe to validate
the native path instead of assuming a `Performance.prototype.now` actor
wrapper.

## Documentation changes

Update the actor inventory and fingerprint coverage documents to distinguish:

- native performance-timeline presentation coverage;
- event-loop callback jitter that remains in `CloakfoxTimingChild`;
- SAB throughput masking and its real-time-thread limitation;
- the difference between fingerprint masking and strong timer elimination.

## Implementation boundaries

The implementation plan should split the work into independently verifiable
stages:

1. performance-timeline tests and the native timing helper;
2. migration of `performance.now()` from the actor to the native helper;
3. complete entry-field coverage and coherence tests;
4. SAB correctness and fingerprint probes;
5. bounded worker execution variation;
6. regression, performance, and documentation gates.

No stage may claim the SAB gap closed unless both the distribution-level
masking probe and the compatibility/performance guardrails pass.
