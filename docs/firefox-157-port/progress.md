# Firefox 157 port progress

Branch: `codex/firefox-157-port`, isolated managed worktree. Existing 146 and 155 checkouts and profiles remain untouched.

## Current state

- Official Firefox 157.0.1 archive matches Mozilla’s SHA-512 manifest.
- Reconciled 155 source and 109 newer 146 files; source hashes and conflict resolutions are in `146-reconciliation.json`.
- All 102 active patches pass an independent pristine-target replay with zero hash drift against the build tree (`check-results.json`, `check.log`). Two superseded 146 patches are archived outside patch discovery.
- Configure passes with Mozilla clang and existing cbindgen 0.29.4 (`local-build.mozconfig`).
- Current Node suite: 218/218 pass. Python native/source harnesses: 11/11 pass.
- Captured 155 baseline: 193 Node tests and 10 Python tests pass. The initial baseline attempt before native source staging was invalid and is not counted.
- Native worker and window Math cache site derivation. The native regression covers 10,000 repeated calls, regeneration, removal, site and container transitions.
- Settings retain the 155 sidebar, profile previews and modular privacy/network/workspace controls, with current 146 presets, appearance and hardware-family sampling reconciled. Runtime verification passes (19 selected live probes plus 6 checks on the mounted DMG).
- Native macOS arm64 build and packaging pass. Ownership calls use `GetRelevantGlobal`; the removed viewport accessor uses `TopInnerSizeSpoofedForRFP`. All corrections are recorded in owning patches.

## Build evidence and staging correction

The first combined stack had 104 patches: 84 passed and 20 failed (`initial-stack/`). Those failures were repaired against pristine 157 targets. The source staging cleanup also removed legitimate vendored `.orig` files; 560 were restored directly from the official archive. Some vendor manifests name files absent from Mozilla’s archive, but Cargo compilation now succeeds. No checksum checks were disabled.

The second build’s output is preserved in `build-attempt-2.log`; `build.log` records the current attempt. A WIP commit preserves the reconciled patch stack: `8c5e4528d0`. The captured 155 input is `be1ce21cd5` with 3,086 hashed files.

## Completed verification and artifact

- 2026-10-11 follow-up: restored the 146 clear-overrides-during-generation
  checkbox. Its regression probe passes against the built app and updated DMG;
  all 218 Node tests pass. See `clear-overrides-verification.md` for behavior,
  source/resource hashes and the updated package checksum.

- 19 selected disposable-profile live probes pass; 6 packaged-app probes pass from the read-only mounted DMG. Latest results and initial failed attempts are retained separately.
- Native appearance startup selection passes all 7 xpcshell cases. Appearance switching preserves the source app, extension origin and profile.
- Production runtime fixes: two SessionStore module URLs and the appearance adapter’s stale popup badge selector. A new unit test demonstrated the badge failure before the fix.
- Three restored 146 probes needed current 155 contracts: fresh-generation UI controls, process-neutral OS locale, and full-secret/site-bound container noise. The old locale/container expectations also failed against the retained 155 binary; these were test fixture repairs, not new engine policy changes.
- Independent review found no verified important regression in the reviewed areas (`review.md`).
- DMG: `cloakfox-157.0.1-beta.25.en-US.mac.dmg`, macOS arm64, approximately117 MB. Hashes and bundle metadata are in `artifacts.json`; final source hashes are in `final-input-hashes.json`.

This is a development package. It launches in the recorded local probes; it is not a notarized release. Strict bundle signature verification reports the development bundle lacks a resource seal (`package-signature.log`). No release signing, update distribution, real Cloudflare challenge or external assessment validation was performed. The subsequently audited upstream follow-up fixes are now applied; see `upstream-followup-verification.md`. Existing provider-key readiness remains false in both loose and packaged startup checks.


Storage cleanup reclaimed 25.3 GB from rebuildable artifacts, redownloadable archives and browser caches; source work, profiles and current builds were preserved (`storage-cleanup.json`).

## Camoufox follow-up fixes — 2026-10-11

- Five additional native patch files cover WebGL/live state and owner principals, analyser scratch-copy noise, configured speech error handling, stock resources and the Windows manifest. Rust Linux vendor normalization was already present and behavior-tested.
- Stack now 107 patches; selective pristine replay has no offset/fuzz/native drift. Node 218 passed; Python 17 passed (16 opt-in cases skipped). Local native/site/container and generation-checkbox probes pass.
- Final development DMG rebuilt and verified directly from a read-only mount. Native build UUID matches the packaged library; resource inventory, native regressions, speech controls and generation checkbox pass. Fresh code review found no issues.
- Hashes, limitations and logs: `upstream-followup-verification.md`, `upstream-followup-packaged-check.json`, `artifacts.json`.
