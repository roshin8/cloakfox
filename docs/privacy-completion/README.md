# Privacy completion — Firefox 155.0.1

Implemented and verified in `codex/firefox-155-compat` on macOS arm64. The original
checkout was left unchanged. No commit, merge, release signing or publication was
performed. Machine-readable results and artifact hashes are in
[verification.json](verification.json).

## Implemented

- **Tracking links and bounces:** native query stripping starts with the bundled
  conservative parameter list before Remote Settings finishes initialization.
  Real navigation preserves OAuth state, code and redirect parameters. Bounce
  protection purges candidate storage; one-day UI exceptions are scoped by
  container and private context independently of ordinary permission-sharing
  preferences. Removing exceptions and deleting/forgetting identities clears the
  corresponding grants. Existing Firefox cookie/tracking exceptions keep their
  native behavior.
- **DNS:** browser-wide system, encrypted-with-fallback and encrypted-only modes.
  Resolver URLs must use HTTPS; encrypted-only mode requires a numeric bootstrap
  unless the endpoint itself is numeric. Native guards reject fallback and
  excluded-name lookups, including queued A/AAAA and native HTTPS/SVC dispatches.
  Already-dispatched OS requests and existing connections cannot be recalled.
  Required proxies continue resolving destination names through the proxy.
- **Permissions:** native stored camera, microphone, location and notification
  grants can be revoked or shortened to timed/session expiry. Stale records and
  managed grants are protected. Temporary tab grants remain in Firefox's tab
  controls; an already-active stream/watch may need stopping in its tab.
- **Workspaces:** create and open real independent Firefox profiles. Live tests
  verify isolated cookies, passwords, history, installed extensions and settings
  across A/B/A restarts, plus the actual native child launcher. Tests isolate
  `profiles.ini` with `MOZ_APP_DATA` and `MOZ_LOCAL_APP_DATA`; owned child cleanup
  checks the exact executable, parent PID and unique profile name.
- **Workers:** dedicated, shared and service workers initialize with coordinated
  locale/timezone/headers. Existing workers observe native privacy-policy updates,
  exception removal and expiry without changing identity secrets. Oversized
  configs are refreshed through authoritative main-thread IPC; workers read
  locked snapshots. Startup-shared preferences cannot overwrite newer snapshots.
  Existing Intl objects and script-cached results still require recreation.
- **Personas and fonts:** new identities sample complete BrowserForge tuples
  conditioned on the host OS. Existing identities retain legacy appearance until
  explicitly changed. Pinned previews/templates use the same mode. All 31 existing
  substitute fonts have verified hashes, actual attribution and packaged licenses;
  no new font binaries or claim of cross-OS rendering indistinguishability.
- **Encrypted backup v2:** includes regions, privacy policies, opening pages,
  persona mode and proxy references. V1 remains readable. Missing proxy references
  restore blocked. Cross-OS host-mode imports explicitly warn that seeds are kept
  while appearance adapts, with a persistent notice. Backups contain identity
  settings, not profile history, cookies, credentials or site-permission grants.
- **Release integration:** owner MAR trust-key preparation, native signed-MAR
  verification and update XML generation; macOS owner Team ID support; release CI
  engine-freshness checks against Mozilla's live feed. Certificate checks compare
  public keys, and offline freshness fixtures cannot claim release readiness.
  Safe Browsing status inspects real local lists and last successful provider
  updates instead of treating preferences as evidence of protection.

## Verification

- Native build passed: [build-3.log](build-3.log).
- 183 Node tests passed, zero failures/skips: [node-tests.log](node-tests.log).
- 28 release Python tests and four network Python tests passed; additional native
  worker-cache/canvas-policy compilation checks passed. Three native-source tests
  also pass in a clean directory containing only tests and the shipped patch.
- All **22 browser probes passed** in [final-probes](final-probes/) and
  [final-regressions](final-regressions/). Each log is indexed in verification.json.
- All **83 patches apply**, and **198 native/source files match** fresh patched
  Firefox: [stack-final.log](stack-final.log),
  [source-verification.json](source-verification.json).
- Independent read-only review found no actionable defect in the reviewed scope:
  [review.md](review.md).

Network probes use local services: real HTTPS DoH A/AAAA answers and failure
controls, native IPv6 HTTP, proxy refusal/recovery, accepted TCP speculative
connections and negotiated HTTP/3 with UDP counters on separate endpoints. The
HTTP/3 fixture trusts an ephemeral CA and disables Firefox's automatic H3 fallback
for third-party roots **only in the disposable test profile**; certificate
validation remains enabled. Negative socket/UDP observations are bounded to two
seconds after the relevant request/control. They are not a system-wide packet
capture or proof against every possible network side channel.

Bounce tests exercise real clearing after injecting native test candidates and
user activation; they do not validate the full heuristic classifier or elapsed
production timer scheduling. Live testing here is macOS arm64, not Windows/Linux.

To reproduce the browser suite, use a Python environment with Selenium and
`tests/network/requirements-h3.txt`, set `CLOAKFOX_BIN` and `GECKODRIVER`, then run:

```sh
python tests/fingerprint/run_daily_driver.py --output /tmp/cloakfox-privacy-probes
node --test tests/fingerprint/test_*.mjs tests/release/test_*.mjs
python -m unittest discover -s tests/release -p 'test_*.py'
python -m unittest discover -s tests/network -p 'test_*.py'
```

## External activation still required

This development build does **not** have functioning automatic browser updates or
downloaded Google Safe Browsing lists. Activation needs owner MAR keys, HTTPS
hosting, platform code signing/notarization and a working provider key, followed
by actual signed-update installation/tamper/wrong-key/rollback/interruption and
provider-download acceptance checks. Windows Authenticode integration remains
unactivated and untested. See [authenticated updates](../release/authenticated-updates.md).
No production credential, placeholder key or test signing root was installed.
