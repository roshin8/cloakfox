# Local checkpoint — 2026-10-16

This is unfinished development work, not a release. Installed app and DMG were not replaced. Full privacy parity remains release-ineligible; no complete policy groups are claimed.

## Workspace

Continue in `/Users/zeus/.codex/worktrees/firefox-158-port/cloakfox`, branch `codex/firefox-158-port`. Read CLAUDE.md and the 2026-10-16 Chromium parity plan/spec. The main Documents checkout is the older 146 tree. Preserve existing work. Use headless/background tests; do not manipulate the user's active windows.

## Latest increments

- Native Select All with strict route/config validation and no clipboard access.
- Private input-routing counters, without text or field identifiers.
- Narrow initial ASCII typing repair, preserving pending password/IME isolation.
- Separate nonnumeric `Default` startup control profile, pinned before CEF startup. Numeric user-container profiles and immutable snapshot rejection remain intact.
- Password fixture and deterministic restart regression.
- Synchronous pointer-focus ownership fence before CEF `mouseDown` on the probe/windowless input path: it bumps the per-browser editing epoch and re-emits the host invalidation, so a metadata reply already in flight for the old focus target cannot be accepted after a click that may move focus. It never restores an old focus and does not relax field/document validation. Client-only; the native framework is unchanged.
- Same-window typing probe gained `--expect-typed-sequence`, so a final Select All + replacement can no longer hide a dropped intermediate accent/dead-key commit.
- `test_same_field_password_transition_invalidates_cached_input_state` no longer assumes the first state query carries metadata; it waits for the settled state, matching the documented "a query retires while fresh focus/type metadata is in flight" behavior.

## Verification (2026-10-16 continuation)

Full native engine suite, first run after the startup-profile fix: 156 tests, one error (the owned-IME state-query test race fixed below), 138.8 s. Log: `/Volumes/CloakfoxChromiumBuild/source-build/logs/continuation-engine-tests-20261016.log`.

Full native engine suite after the pointer-focus fence: **156 tests passed**, 129.6 s. Log: `/Volumes/CloakfoxChromiumBuild/source-build/logs/continuation-engine-tests-afterfix-20261016.log`. This supersedes the earlier 155-test run with 12 failures and one error: the inventory refresh and restart-collision fix already cleared them, and no shutdown-watchdog teardown failure appeared in either full run.

Stale cross-frame metadata probe (`tests/engines/probe_owned_ime_state_order.py`): an accepted stale reply reproduced 2/10 before the fence and 10/10 clean after it. Logs: `continuation-stale-frame-repro-20261016.log`, `continuation-stale-frame-afterfix-20261016.log`.

Shutdown-watchdog stress (15 windowed open/quit cycles on disposable roots): 15/15 clean, slowest shutdown 0.62 s against the 10 s watchdog. Log: `continuation-shutdown-stress-20261016.log`. The intermittent teardown failures seen before the startup-profile fix did not reproduce; no watchdog, test, or security check was weakened.

Pipeline acceptance stages, all passing on the fixed binary: CTest `container_paths` + `surface_transport` 2/2; `probe_cef_isolation` (initial+restart isolation, renderer sandbox, camera/mic/location denial); `probe_cef_transport` (`certificateVerificationDisabled=false`); `probe_dual_engine_coexistence` (Gecko 158 beta + CEF 154 concurrently, shared owned origin). Log: `continuation-pipeline-stages-afterfix-20261016.log`.

Complete native-engine harness (`engines/chromium/build_identity.py`) also reran end to end. One run failed in `engine-tests` on a single load-induced shutdown-watchdog teardown expiry (`test_webgpu_pixel_privacy.test_disable_keeps_rendered_pixels_exact`): the test body passed, but `close()` observed `returncode 2` with "Teardown watchdog expired". The system load average was 12–21 and that suite took 234 s versus ~130 s normally. Preserved log: `continuation-pipeline-teardown-failure-20261016.log`. The same WebGPU module then passed 8/8 (13–16 s each) once load eased, and the 15-cycle windowed open/quit stress passed 15/15 (slowest 0.62 s). No leaked companion or helper process was found, and the client releases all browser/context/DevTools-observer refs before `CefShutdown`, so no client-side shutdown-ordering defect was identified; the researched browser/window destruction ordering problem remains unproven. Do not raise the watchdog or relax the test.

A subsequent full harness run (`continuation-full-pipeline-2-20261017.log`) passed end to end: `owned-editor-build-status.json` is `state=passed`, `lastPassed=gecko158-coexistence`, `runtimeTestsPassed=true`, 156 engine tests in 123.4 s, framework SHA `7b2a1d9a...` unchanged.

## Remaining limits

- Real macOS IME/accent/dead-key input and same-window UI acceptance are still not exercised here; they need an explicit live-UI window and must not be run from background tests. The strengthened `--expect-typed-sequence` assertion is ready but has not yet run against a live typing flow.
- The fence closes the reproduced pointer-driven race but does not eliminate the general browser-focus-lag window. A renderer-acknowledged native focus transaction remains the correct long-term design for reliable queued-input replay; research only, not implemented.
- Remaining Chromium privacy policy groups, full same-window/separate-window integration, and the final independent review of the whole port are unfinished. `releaseEligible` stays false.
- The native CEF framework hash is unchanged: `7b2a1d9a925fd91685af30bfadaae61e70ca480f372ac9ac84e7c67c6ef07b85`.

## Build artifacts

External drive must remain mounted. Build root: `/Volumes/CloakfoxChromiumBuild/source-build`.
Current development client: `owned-editor-companion-build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium` under that root.
Do not install the diagnostic owned-editor-ui-candidate bundle: deep signing verification failed. No release artifact is approved.

Generated historical evidence logs and live fixture reports remain outside this code checkpoint where untracked. External build logs remain on the build drive. The ignored .superpowers progress ledger remains local; this tracked handoff records the latest state.
