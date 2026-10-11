# Fingerprint tests

## Letterboxing / native window geometry

```bash
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_letterboxing.py
```

Uses a disposable profile and local HTTP pages. Checks responsive browser chrome,
shared viewport buckets, JavaScript/CSS/screen/visual-viewport agreement, same-
and cross-origin frames, multiple containers, scroll offsets, reload/navigation,
cursor default, and live master/letterboxing switches. `GECKODRIVER` may specify the driver binary;
otherwise it must be on PATH. The probe asserts that Cloakfox actually launched.

Letterboxing is enabled by default independently of global RFP (which stays off).
While enabled, native geometry ignores saved persona viewport/screen dimensions:
the actual content viewport drives layout and the protected screen dimensions.
The tabs and toolbar retain Firefox's normal flexible sizing. Disabling
`privacy.resistFingerprinting.letterboxing` restores legacy persona geometry,
but never restores the physical browser-window size hijack.

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

## Firefox 155 compatibility regressions

`probe_media_capabilities.py` checks decoding and encoding hooks independently,
native fallback for unsupported formats, and rejection of invalid inputs. It
uses disposable profiles and a local HTTP page.

`probe_webgl_readback.py` checks deterministic seeded pixel reads and canvas
exports (`toDataURL` and `toBlob`), plus native Firefox canvas randomization
when Cloakfox is disabled or the canvas seed is absent.

`test_canvas_extraction_policy.py` and `test_webgl_async_readback.py` run without
a browser and compile the production policy/noise helpers. Both run in CI.

`probe_worker_canvas.py` compares the same font-free OffscreenCanvas drawing
in windows and dedicated workers across four containers, including a zero
seed, and checks pixel/blob hashes remain stable after reloads.

`test_cpp_first_worker_cache.py` compiles the production preference-reader helper
and checks that worker reads use cached container configuration without touching
main-thread Preferences or IPC APIs. It also runs in CI.

`probe_about_dialog.py` opens the custom chrome dialog and checks the displayed
build version, absence of dialog errors, and close-command handling under the
current content security policy. It dispatches the command directly; it does
not simulate a physical Escape key press.


## Daily-driver privacy checks

After a native build, run the disposable-profile suite sequentially:

```sh
CLOAKFOX_BIN=/absolute/path/to/cloakfox python run_daily_driver.py --output /tmp/cloakfox-daily-results
```

Use the Selenium virtualenv and geckodriver described above. The suite covers
persistent defaults, engine-version migration over HTTP and JavaScript, the
bundled signed blocker and user removal, proxy failure and native bypass handling,
WebRTC policy and local STUN packets, container data/restore clearing, shared
permission preservation, site-bound outputs, and container/backup workflows.
It uses disposable profiles. The blocker test restores production addon defaults
that geckodriver otherwise disables. The WebRTC packet test explicitly enables
loopback ICE in its test profile to obtain a meaningful positive control.

Safe Browsing preferences alone do not establish working provider lists; the
suite reports missing provider configuration. Automatic browser updates also
remain unavailable until owner-controlled release signing and hosting are
configured. See `docs/daily-driver-privacy/` for implementation and evidence.


## Camoufox upstream hardening (September 2026)

```bash
python tests/fingerprint/test_upstream_hardening.py
node --test tests/fingerprint/test_mediaquery_logic.mjs tests/fingerprint/test_webrtc_lookup.mjs
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python tests/fingerprint/probe_upstream_hardening.py
```

The native snippet tests require the applied Firefox source tree, a C++17
compiler, and Node. They execute the real shaping loop, voice-registration gate,
font filtering helpers, generic/emoji cache resolution, and SessionStore method. Assertions cover horizontal and
vertical glyph advances without changing shaping offsets; native voice admission
with absent/false/true flags; chrome/internal font exemptions and owner-container
selection; and tracked/untracked SessionStore windows.

The live probe requires Selenium/geckodriver and disposable profiles. It checks
page/iframe setter absence, privileged Xray access, actual rendered font families
via InspectorUtils, native chrome CSS2 fonts, different container personas,
Touch/TouchEvent plus CSS/JS pointer agreement at zero/five touch points, and
native voice registration with a sentinel positive control. An Arial-only
container exercises last-resort fallback. It never speaks audio.
This probe is included in `run_daily_driver.py`.


## Region, policies, templates and proxy manager

The daily runner includes `regions`, `privacy_inspector`, `proxy_manager`, and
`templates`. Run them sequentially against a rebuilt browser:

```sh
CLOAKFOX_BIN=/absolute/path/to/cloakfox python tests/fingerprint/run_daily_driver.py \
  --output /tmp/cloakfox-controls --only regions --only privacy_inspector \
  --only proxy_manager --only templates
node --test tests/fingerprint/test_*.mjs
```

These probes use local servers and disposable profiles. Region measurements run
in page-owned functions, because Selenium's sandbox has its own Date/Intl realm.
The region probe checks document and dedicated-worker headers/languages/locale,
DST, explicit locales, denied/granted coarse location, and container switching.
Policy coverage checks vector/site/container isolation, expiry, unchanged seeds,
actual inspector window/worker measurement, reversible repairs and UI loading.
The proxy probe uses local HTTP Basic and SOCKS5 fixtures, including rejected
credentials, connection reuse isolation, proxy DNS and no direct fallback. It
never logs credentials. Template coverage checks persisted settings before page
opening, fresh secrets and empty site data, proxy-required failure, redacted
exports and restart stability. Inspector unit tests also cover stale repair/undo
and exclusion of private windows.

HTTP authentication intentionally supports Basic only. Diagnostics require an
explicit HTTPS endpoint and report reachability, not exit IP or location.
New controls do not provision any external account or service.


### September 2026 privacy completion probes

`run_daily_driver.py` now includes native tracking/bounce protection, HTTPS DoH,
IPv6/speculative transport checks, HTTP/3 UDP controls, worker startup/live policy,
host persona mode and isolated profile workspaces. Install
`tests/network/requirements-h3.txt` alongside Selenium for the full runner.
The workspace probe isolates app-data directories and cleans up only its owned
native test child. See `docs/privacy-completion/README.md` for evidence and exact
coverage limits. The identity workflow probe exercises encrypted v2 and v1 import.
