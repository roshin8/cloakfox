# Fingerprint tests

Two tools for validating the H2/H3 transport-fingerprint patches land as
designed and match the browser they claim to mimic.

## 1. `test_h2_profile.py` — automated shape check

Launches the built Cloakfox binary under each H2 profile (firefox / chrome /
safari) via **Selenium + geckodriver**, hits `https://tls.peet.ws/api/all`,
and asserts the SETTINGS frame, WINDOW_UPDATE, and HPACK pseudo-header order
match each profile's spec.

### Why Selenium and not Playwright

Playwright's Firefox driver uses the Juggler protocol, which requires a
Juggler-patched Firefox binary. Playwright ships one; Cloakfox does not.
Attempting `playwright.firefox.launch_persistent_context(executable_path=CLOAKFOX_BIN)`
times out after 180s waiting for a Juggler handshake that never comes.

geckodriver speaks Marionette — the WebDriver protocol that every Firefox
build (vanilla, LibreWolf, Cloakfox, Camoufox) supports by default. No patch
required.

### Setup

```bash
pip install pytest selenium
brew install geckodriver          # macOS
# or download geckodriver from https://github.com/mozilla/geckodriver/releases
```

### Run

```bash
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

On Linux, point at the built-in-tree binary:

```bash
CLOAKFOX_BIN=$(pwd)/firefox-src/obj-x86_64-pc-linux-gnu/dist/bin/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

Skips cleanly when `CLOAKFOX_BIN` is unset — CI can run the test suite
without blowing up on machines without a built binary.

### What each test checks

- `test_h2_profile_shape[firefox]` — SETTINGS {1,2,4,5}, HPACK order `:method, :path, :authority, :scheme`.
- `test_h2_profile_shape[chrome]` — SETTINGS {1,2,3,4,6} with MAX_CONCURRENT=1000, INITIAL_WINDOW=6291456, MAX_HEADER_LIST=262144; WINDOW_UPDATE=15663105; HPACK order `:method, :authority, :scheme, :path`.
- `test_h2_profile_shape[safari]` — sparse SETTINGS {2,3,4} with MAX_CONCURRENT=100, INITIAL_WINDOW=2097152; WINDOW_UPDATE=10485760; HPACK order `:method, :scheme, :path, :authority`.
- `test_h2_profiles_produce_distinct_fingerprints` — all three profiles produce distinct `akamai_fingerprint_hash` values. Collapsing hashes mean the WebIDL setter isn't firing OR `cloakfox.cfg` is clobbering user prefs (see gotcha below).

### One shared probe per session

The three shape tests and the distinct-fingerprints test share a single
session-scoped fixture that launches Cloakfox once per profile. This makes
the full suite run in ~6 seconds against a local build.

### Known limitations

- **Headless is OK** for this test — we only care about wire-level bytes,
  not JS-level MAIN-world spoofing. Tests that check `navigator.*`, canvas,
  etc. would need headful.
- Geckodriver prints its log to `<tmp>/gd-<profile>.log` if you need to
  debug why a launch failed.

### Why the `pref()` vs `defaultPref()` matters (gotcha)

The AutoConfig file `settings/cloakfox.cfg` originally declared:

```
pref("network.http.http2.fingerprint_profile", "firefox");
```

In Mozilla's AutoConfig semantics, `pref()` overwrites the user value on
every startup. So if the extension (or a test, or an about:config edit)
flipped the pref to "chrome", the next startup reset it to "firefox" and
the patch emitted Firefox-default SETTINGS. The test caught this with
`test_h2_profiles_produce_distinct_fingerprints` failing — all three
profiles produced identical hashes.

Fix: use `defaultPref()` for toggleable prefs. This only seeds the default
value; the user value (set by `Preferences::SetCString` via the WebIDL
setter, or by `set_preference` in the test) survives restart.

## 2. `mitm_h2_observer.py` — local packet-level observation

A mitmproxy addon that prints the exact H2 SETTINGS frame, WINDOW_UPDATE
value, and HPACK pseudo-header order Cloakfox emits per connection. Use
when you want to see bytes on the wire, not a remote service's interpretation.

### Setup

```bash
pip install mitmproxy  # 10+ required for H2 introspection
```

### Run

```bash
mitmproxy -s tests/fingerprint/mitm_h2_observer.py --listen-port 8080
```

Then in Cloakfox, `about:config`:

```
network.proxy.type                 = 1
network.proxy.http                 = 127.0.0.1
network.proxy.http_port            = 8080
network.proxy.ssl                  = 127.0.0.1
network.proxy.ssl_port             = 8080
network.proxy.share_proxy_settings = true
```

Visit any `https://` site that speaks H2. mitmproxy prints a block per new
connection:

```
─── 192.0.2.1:443 ──────────────────────────────────────
SETTINGS:
  HEADER_TABLE_SIZE          (1) = 65536
  ENABLE_PUSH                (2) = 0
  MAX_CONCURRENT             (3) = 1000
  INITIAL_WINDOW_SIZE        (4) = 6291456
  MAX_HEADER_LIST_SIZE       (6) = 262144
WINDOW_UPDATE: 15663105
HPACK order on first HEADERS: :method, :authority, :scheme, :path
```

### HTTPS interception note

mitmproxy intercepts TLS by injecting its own CA cert. Install mitmproxy's
cert (`http://mitm.it/` from a proxied browser) so Cloakfox trusts the
intercepted connections. This is pure local observation — nothing about
the cert manipulation leaks the real fingerprint.

## Shared-memory privacy diagnostic

`probe_sab_privacy.py` measures clock recovery through a worker's shared-memory
counter during synchronous low/high fixed workloads. It runs both worker and
main-thread observers, saves raw samples, and fits a classification threshold on
the first half before scoring the held-out second half. The counter yields
between finite batches, allowing serialized execution to progress without a
busy-wait handshake.

```bash
tests/.venv/bin/python tests/fingerprint/probe_sab_privacy.py \
  --binary /Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  --output /tmp/sab-privacy.json
```

The native, experimental jitter, and Firefox serialized-access policies each
use a fresh profile with a valid timing key. Reports record installed browser
version/build metadata and whether the requested mechanism has a registered
default preference; writing an unknown preference is not evidence of support.
An absent mechanism is inconclusive. An installed older browser cannot validate
the current unbuilt branch.

These measurements are diagnostics, never privacy PASS results. A functioning
native positive control is needed to interpret reduced clock recovery under a
policy; a native result near chance means the experiment lacks sensitivity.
Even zero observed counter advancement does not establish resistance to other
clocks, repeated statistical attacks, hardware identification, or recognizing
the serialization policy itself. Policy order, thermal state, and background
load can influence samples; replicate with reversed `--policies` order for
comparisons. The aggregate regression runner explicitly skips this diagnostic.

## What lives where

```
tests/fingerprint/
├── README.md                — this file
├── test_h2_profile.py       — Selenium E2E: launches Cloakfox, hits peetwapp
└── mitm_h2_observer.py      — mitmproxy addon: logs H2 frames locally
```

## Live verification output (reference)

Run against a build at `unified-maskconfig@2195549a9c`:

```
firefox: 6ea73faa8fc5aac76bded7bd238f6433 | 1:65536;2:0;4:131072;5:16384 | WU=12517377 | m,p,a,s
chrome : a345a694846ad9f6c97bcc3c75adbe26 | 1:65536;2:0;3:1000;4:6291456;6:262144 | WU=15663105 | m,a,s,p
safari : c9da4b13f7b57d7e7082044bd0f7225c | 2:0;3:100;4:2097152 | WU=10485760 | m,s,p,a

============================ 4 passed in 6.29s ============================
```

## 3. `test_h3_profile.py` — H3 profile pref plumbing

Verifies the HTTP/3 fingerprint profile pref round-trips through Firefox's
static_prefs system. Wire-level observation of the QUIC SETTINGS frame
would need mitmproxy-quic / wireshark — out of scope here. Instead this
test proves: (a) the default pref is 0, (b) setting via prefs.js survives
browser startup (defaultPref contract), (c) the `setHttp3Profile` WebIDL
method is bound on windows.

Documents a known limitation in its header — the WebIDL setter's
`Preferences::SetUint` call runs in content-process scope and doesn't
persist to the parent prefs DB without IPC. Selenium/prefs.js is the
working path today; a WebExtensions Experiment API is the follow-up.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_h3_profile.py -v
```

## 4. `test_sec_ch_ua.py` — Sec-CH-UA HTTP header injection

Checks the webRequest header-spoofer emits `Sec-CH-UA`, `Sec-CH-UA-Mobile`,
`Sec-CH-UA-Platform` headers when the assigned profile is Chromium, and
does NOT emit them for Firefox/Safari profiles. Documents the cold-start
race: first navigation in a session can't have CH headers because the
inject script hasn't posted the active profile yet.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_sec_ch_ua.py -v
```

## 5. `test_math_constants.py` — Math.PI / Math.E / etc. determinism

Four tests: perturbation (not IEEE), in-session determinism, cross-domain
differentiation, Math.sin is noisy too. Uses DOM-injection pattern because
selenium's `execute_script` sandbox maintains a separate `Math` binding
from the page's.

```bash
CLOAKFOX_BIN=... pytest tests/fingerprint/test_math_constants.py -v
```

## 6. `antibot_battery.py` — pre-release validation tool (not pytest)

Drives Cloakfox through bot.sannysoft / areyouheadless / browserleaks /
CreepJS under each of the three transport profiles, captures full-page
screenshots, extracts verdicts where possible, emits a markdown report.
Not wired into pytest — runs for minutes and depends on external sites.

```bash
CLOAKFOX_BIN=... python tests/fingerprint/antibot_battery.py
```

Output at `tests/fingerprint/reports/<timestamp>/REPORT.md` with inline
screenshots.

## 7. Native performance timeline coverage

`probe_timing_jitter.py` and `probe_performance_timeline.py` separate the
two timing owners deliberately:

- **Gecko owns `performance.now()` and every performance-entry presentation.**
  Native `Performance::PresentTimestamp()` and `Performance::PresentInterval()`
  present the reduced clock and entry timestamps; no page-world actor wraps
  `performance.now()`.
- **`CloakfoxTimingChild` owns only callback jitter.** It retains the
  `setTimeout`, `setInterval`, and `requestAnimationFrame` wrappers: timeout
  and interval scheduling receive up to 2 ms of jitter, and rAF callback
  timestamps receive sub-millisecond noise.

The timeline probe exercises `PerformanceObserver` and all eight entry types
Firefox 146 advertises here:
`event`, `first-input`, `largest-contentful-paint`, `mark`, `measure`,
`navigation`, `paint`, and `resource`. It compares observer callbacks,
direct getters, `getEntries*()`, and `toJSON()` for stable presentation of
`startTime` and `duration`, plus these additional timing fields where the
entry exposes them:

- event timing: `processingStart`, `processingEnd`;
- paint and LCP: `paintTime`, `presentationTime`, `renderTime`, `loadTime`;
- resource and navigation: `workerStart`, redirect/DNS/connect/request/
  response phases, and navigation's unload, DOM, and load-event phases.

An automatically timestamped mark uses Gecko's presented clock. Explicit User
Timing values are compatibility inputs, not noise targets: a supplied mark
`startTime`, or a measure's explicit start/end and resulting duration, must be
returned exactly. The timing key is stable for one browser session and is
container-specific; a new browser session or a different container receives a
different key. This coverage does not claim SharedArrayBuffer timing coverage.

## 8. Shared-memory worker timing experiment

`probe_sharedarraybuffer_timing.py` preserves and directly checks the
`SharedArrayBuffer`, `Atomics`, and shared WebAssembly APIs and their exact
values. With no arguments it runs the safe literal-default correctness check;
the experimental scheduler can be exercised explicitly with
`--mode correctness --correctness-masking enabled`. Dedicated workers ran on
this build. SharedWorker and ServiceWorker reported that their realms were not
cross-origin isolated and were recorded as capability-backed skips.

The implementation is eligible only for non-chrome, non-privileged
`WorkerPrivate` workers where shared memory is allowed and the worker is
cross-origin isolated. Worklets and audio render threads are excluded. It
adds a deterministic, bounded scheduling perturbation to worker throughput;
it is not universal SAB-clock elimination and is not Spectre mitigation.

The performance gate passed: disabled median 12.063449 ms, enabled median
11.976487 ms, or -0.7209% versus the +5% cap. The post-performance efficacy
gate did not: disabled median/MAD was 112,664,483/1,218,913 and enabled was
109,611,994.5/683,119. The center criterion passed, but the required spread
increase failed. Consequently `cloakfox.sab_worker_timing_masking` is an
emergency/experimental rollback pref that remains `false` by default, and
SharedArrayBuffer timing is not marked covered.

## Gotchas we hit (and documented in tests)

Writing these tests surfaced several real bugs in the shipped build,
each worth remembering:

1. **`jar.mn` paths must match `manifest.json`.** Previously the jar
   packaged files under `dist/inject/index.js` but manifest said
   `inject/index.js` — Firefox silently skipped registering the content
   script and no JS-level spoofing ran in ANY shipped build. Fixed by
   flattening the `dist/` prefix from jar.mn destinations.

2. **AutoConfig `pref()` clobbers user values.** `cloakfox.cfg` was
   using `pref()` for the H2/H3 fingerprint toggles, which in Mozilla
   AutoConfig semantics overwrites the user pref on every startup.
   Must use `defaultPref()` so user values (set via selenium, extension,
   or about:config) survive restart.

3. **Math.PI is non-writable non-configurable per ECMA spec.** You
   can't Proxy-wrap Math and return a different PI — the proxy invariant
   for non-writable non-configurable properties demands the same value.
   Any access throws TypeError. Workaround: build a plain object with
   writable constants and replace `window.Math`.

4. **Double XOR cancels the domain contribution to the seed.** The
   inject script's fallback `generateSeed(domain)` XOR-folded domain
   into the seed, then `initializeSpoofers()` XOR'd the domain in AGAIN
   to derive the page PRNG. Domain bits cancel; every fallback page
   gets the same PRNG. Fixed by dropping the domain from generateSeed
   — let the spoofers module be the only place domain is XOR'd.

5. **Noise must exceed float64 ULP to be visible.** My first Math
   constant spoofer used 1e-15 noise. Math.PI's ULP is ~4.44e-16 — a
   1e-15 perturbation rounds to zero half the time, producing IEEE-
   identical bit patterns and defeating the spoof. Bumped to 1e-13
   (~225 ULPs — guaranteed visible, still invisible numerically).

6. **WebIDL setters from content process don't persist prefs.**
   `Preferences::SetCString/SetUint` called from a WebIDL method runs
   in content-process scope. In e10s Firefox the parent owns the prefs
   DB; content writes don't persist without IPC. The `setHttp2Profile`
   / `setHttp3Profile` methods self-destruct (proving they were called)
   but the pref doesn't actually change. Real toggle path is via
   profile prefs.js or about:config — not the page-script setter.

7. **Selenium sandbox has its own Math binding.** `driver.execute_script`
   runs in a webdriver sandbox with a separate copy of Math from the
   page. Reading `Math.PI` from selenium gets the IEEE default even when
   the page's Math is spoofed. Workaround: inject a `<script>` tag that
   writes the value to the DOM, then read via `find_element`.

## What lives where

```
tests/fingerprint/
├── README.md                — this file
├── test_h2_profile.py       — H2 SETTINGS/WINDOW_UPDATE/HPACK shape per profile
├── test_h3_profile.py       — H3 pref plumbing
├── test_sec_ch_ua.py        — HTTP header injection
├── test_math_constants.py   — Math.PI/E/LN2 noise
├── mitm_h2_observer.py      — local byte-level observer
└── antibot_battery.py       — manual pre-release validation tool
```
