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

## Verification and limits

Latest focused identity/protocol/bootstrap suites: 14 tests passed, 24.549 seconds. Source log: `/Volumes/CloakfoxChromiumBuild/source-build/logs/bootstrap-focused-suites.log`.
CTest rerun at checkpoint: container_paths and surface_transport both passed (2/2). `git diff --check` passed before staging.

Earlier full owned-editor pipeline failed: 155 tests, 12 failures plus one error. Inventory was refreshed and the restart collision fixed subsequently; full pipeline has NOT been rerun successfully. Several failures were shutdown-watchdog teardown failures rather than failed privacy assertions. Investigate cleanup without disabling watchdog/security checks.

Real native initial ASCII and password input passed targeted checks. Immediate Option/accent/IME input before fresh focus metadata remains unresolved. A final replacement character can hide a missing accent in the current probe; add intermediate assertions. Consider synchronous pointer-focus invalidation before CEF mouseDown, but this is research, NOT implemented. Do not weaken field/document validation to replay unknown queued input.

Scoped static reviews found no actionable issue in the counters/Select All, narrow ASCII gate, and startup control-profile fix. These are not a final review of the entire port.

## Build artifacts

External drive must remain mounted. Build root: `/Volumes/CloakfoxChromiumBuild/source-build`.
Current development client: `owned-editor-companion-build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium` under that root. Current native framework hash remains `7b2a1d9a925fd91685af30bfadaae61e70ca480f372ac9ac84e7c67c6ef07b85`. No native CEF source/framework changes in the latest increment.
Do not install the diagnostic owned-editor-ui-candidate bundle: deep signing verification failed. No release artifact is approved.

Generated historical evidence logs and live fixture reports remain outside this code checkpoint where untracked. External build logs remain on the build drive. The ignored .superpowers progress ledger remains local; this tracked handoff records the latest state.
