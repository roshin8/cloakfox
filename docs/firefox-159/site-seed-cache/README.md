# Firefox 159 native site-seed caching

Implemented bounded memoization of parsed configuration and derived HMAC seeds.
It avoids repeating JSON parsing and cryptographic work for each element rectangle
query. Native algorithms, secrets, returned noise, protection toggles and policy
remain unchanged.

## Isolation and invalidation

- Exact owner ID including default owner0; no ambient-container fallback.
- Separate per-thread state. A worker never reuses another thread's mutable cache.
- Every access still reads the current authoritative overlay. Changed bytes replace
  the entire immutable snapshot, covering seed/secret rotation, configuration edits,
  master toggle, deletion and malformed input.
- Derivations are keyed by vector, base seed and canonical top-level site, within
  the exact owner's configuration/secret. The cache creates no shared identity.
- Policy and the current clock are checked before any hit. An exception cannot
  outlive its expiry; clock rollback also re-evaluates the policy.
- Eight retained owners, 64 derived seeds per snapshot; eviction recomputes the
  same result. Shared references keep an in-flight snapshot valid during eviction.
- Failed HMAC derivations are not cached. Nothing is persisted to disk or uploaded.

## Verification

- Initial regression test failed against the old implementation because 1000
  identical calls repeated HMAC. It passes with caching. Native tests cover exact
  owners, changed sites/vectors/seeds/secrets, expiry, malformed config, retry,
  eviction and worker isolation.
- All 440 JavaScript tests passed. Python suite: 198 passed, 14 optional browser
  tests skipped because that unit-suite invocation had no CLOAKFOX_BIN.
- Firefox159 live cache probe: 37 checks passed, including actual NSS, clock,
  native document ownership, preference propagation, disabled/master re-enable,
  rectangle union consistency and site/container separation.
- Existing live site-isolation and DOM-geometry probes passed. Cross-site outputs
  remain separated, same-site reloads stable, tracker iframe and worker scope
  agrees with the owning publisher.
- Amazon: successful homepage, `usb c cable` search, product navigation and
  protected rectangle workload. Disposable headless profile copied Container #02
  (owner44) definitions, its config/seeds and hardening settings; no cookies,
  credentials or browsing session copied. User's prefs file unchanged at end.
  Each navigation asserts owner44, enabled master, unchanged hardening preferences
  and exact persona config except existing per-session timing keys. Native network
  profile stays fixed while its connection generation can advance.
- Amazon's normal Continue shopping button was clicked when shown. No CAPTCHA
  solver, fingerprint change or privacy bypass was used for the navigation test.
- Independent code review: no open findings. A P2 test assertion gap was corrected
  and reviewed again; see code-review.md.

## Measured improvement

On the same local 2000-call fixture using Container #02's 6062-byte public config,
full-config median 815.60→211.33ms (3.86x), repeated full-config 591.29→164.90ms
(3.59x). Every returned protected width, union width and aggregate was identical.
See performance.json and compressed raw reports. These measurements are local
geometry costs, not a claim that all Amazon network navigation is 4x faster.

The separate baseline Amazon run reached its second Continue shopping checkpoint
after search and is marked inconclusive for end-to-end timing. It is retained in
amazon.json and runtime/amazon-before-inconclusive.json.gz; the completed new-build
run passed. The local before/after benchmark is complete.

## Build and delivery

Native Firefox159 build passed with 0 compiler warnings, two low-priority jobs.
Test app: `firefox-src/.tools159/acceptance-site-seed-cache/Cloakfox.app`.
XUL hash and bundle metadata are in acceptance-app.json. Sources were synchronized
from additions/cloakcfg into the build tree, retaining pre-edit copies under
.tools159/site-seed-cache/source-before.

Applications/Cloakfox.app and the personal session were not replaced/restarted.
The genuine Firefox.app is untouched. No commit, push or new DMG was requested.
Existing uncommitted GPU expansion and other concurrent work were preserved.
Chromium build inputs match the previous checkpoint; no Chromium files, jobs,
outputs or checkpoints were modified or deleted.

## Test fixture corrections retained in receipts

Initial local probe used a shared helper that looked up the first tab with an
identical URL when checking ownership; unique per-owner URLs fixed the fixture.
Early Amazon attempts required the existing MOZ_REMOTE_ALLOW_SYSTEM_ACCESS test
flag, exact selected-tab ownership, and handling the ordinary Continue shopping
prompt. Config equality deliberately excludes only the two native session timing
keys, and network-state equality uses its documented profile-bit/generation
semantics. None of these corrections changed browser protection. Failed-attempt
receipts remain in report directories; successful reports are in runtime/.

## Reproduction

Use the Python environment at firefox-src/.tools159/runtime-venv/bin/python.
Set CLOAKFOX_BIN to the test app's Contents/MacOS/cloakfox, MOZ_HEADLESS=1,
MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1, and REPORT_DIR to a new disposable report folder.
Run tests/fingerprint/probe_site_seed_cache.py, probe_site_isolation.py and
probe_dom_geometry_consistency.py. Amazon probe additionally takes
CLOAKFOX_SOURCE_PROFILE (read-only) and CLOAKFOX_TEST_OWNER=44. It uses a new
disposable profile and never drives the user's running browser.

## Installation — 2026-10-29

At the user's request, installed the tested build into `/Applications/Cloakfox.app`.
Staged a self-contained clone, verified it against the acceptance hashes, signed
using the repository canonical-GPU signing/manifest workflow, and passed all 37
live cache checks against that signed staged copy. Quit the previous app cleanly,
backed up the active profile and app, then replaced only the app bundle.

Relaunch used the original profile and restored 64 tabs with Container #02 selected.
Profile data was byte-identical through replacement; persisted privacy/container
settings were checked after launch. Native connection generation counters advanced
normally without changing their profile bits. See installation.json for verification
and the backup location. Chromium sources, build controls and checkpoints untouched.
