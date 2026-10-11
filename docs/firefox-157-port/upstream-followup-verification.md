# Camoufox follow-up port — Firefox 157

Completed on `codex/firefox-157-port`, 2026-10-11. Product changes are commit `86341bc2f4`. The restored **clear overrides when generating** checkbox is included and verified in this package.

## Upstream scope

Reviewed Camoufox main at [`d01b8b907af0372b5c5a0f338cb94d2b2276db8c`](https://github.com/daijro/camoufox/tree/d01b8b907af0372b5c5a0f338cb94d2b2276db8c/browser/patches). Its patch/test contents match the previously audited `f008b768` revision. Five additional Cloakfox-native patch files adapt the applicable changes:

| Patch | Result |
| --- | --- |
| `cloakfox-webgl-live-state-followup.patch` | Only fixed capability limits use captured tables; mutable render state and context attributes reflect the actual context. Preserves extension/version/error gates, null fallback, configured renderer coherence, and principal ownership for detached/offscreen canvases. |
| `cloakfox-audio-analyser-copy-followup.patch` | Frequency reads transform a fallible scratch copy, preserving FFT smoothing state and existing site/container seeds. |
| `cloakfox-speech-error-followup.patch` | Suppresses backend voice-list errors with an active environment-configured voice list; native errors remain with no configured list or the master switch off. |
| `cloakfox-stock-resource-followup.patch` | Packages stock crash-page resources with crash reporting disabled; removes the development-helper resource, startup load and registration together. |
| `cloakfox-windows-manifest-followup.patch` | Adds the renamed executable's manifest from stock Firefox 157, preserving privileges and supported OS declarations. |

The Rust Linux `pc` → `unknown` vendor normalization was already present in the 157 port. Actual selector regression tests verify that selection, explicit vendor matches, ambiguity errors and Windows ABI choices; no duplicate patch was added. Existing font/touch/SessionStore/privacy work remains intact. The active stack is now **107 patches**.

Automation/Juggler, synthetic capture/codec claims and removal of daily-use features were not imported. Conditional media/voice redesign items from the original audit remain separate work.

## Evidence

- **RED → GREEN:** original native WebGL state/attribute/gating/null-fallback and audio tests failed. The analyser differed by 0.16967 dB before the repair; repeated float reads now agree within 0.00000763 dB and byte reads match. Owner-principal, voice-error, crash-resource and Windows-manifest source regressions also failed before their changes.
- **Native build:** incremental macOS arm64 build succeeds; final build reports zero compiler warnings (`upstream-followup-native-build.log`).
- **Patch replay:** `python3 scripts/verify_patch_replay.py` stages current additions into a separate selective pristine-source fixture and replays all 107 patches: 224 pristine targets, zero offsets, fuzz or native-file hash drift (`upstream-followup-replay.json`). It does not mutate the build source.
- **Unit/source checks:** Node 218 passed; Python 17 passed. The 16 opt-in binary-dependent network/math cases were skipped in that Python run and are not claimed as executed (`upstream-followup-node-tests.log`, `upstream-followup-python-tests.log`).
- **Live native checks:** WebGL 1/2 mutable state, actual attributes, renderer agreement, version/extension errors, fixed limits/null fallback and shader compile/link/draw/readback pass. Analyser smoothing and master-off controls pass. Two containers retain their own identities in attached documents, createHTMLDocument, DOMParser, window OffscreenCanvas and dedicated workers (`upstream-followup-runtime-green.log`).
- **Speech backend controls:** no configured list forwards errors; an active configured list suppresses them; master-off forwards errors in both modes (`upstream-followup-speech-runtime.log`). These are registry notification controls, not synthesized playback tests.
- **Existing privacy controls:** site reload/subdomain stability, cross-site separation, third-party partitioning and worker agreement pass (`upstream-followup-site-isolation.log`). The generation checkbox regression passes (`upstream-followup-generation-runtime.log`).
- **Independent review:** a fresh reviewer checked `9371224db1..86341bc2f4` and the applied native files, including replay hashes. No Critical, Important or Minor findings.
- **Mounted DMG:** resource inventory, native regressions, speech controls and the generation checkbox all pass against the app inside the final DMG. Its XUL hash matches the packaging stage and its Mach-O UUID matches the development build. Packaging strips debug symbols, so the development and packaged XUL byte hashes differ normally. See `upstream-followup-packaged-check.json` and `upstream-followup-packaged-*.log`.

An initial package inventory check caught two obsolete generated development-helper symlinks retained from an earlier incremental build. Those generated symlinks were removed, original source preserved, and the DMG rebuilt. The final package has no helper asset, startup call or category registration (`upstream-followup-stale-resource-cleanup.json`).

## Artifact and limits

DMG: `cloakfox-157.0.1-beta.25.en-US.mac.dmg` (macOS arm64).

SHA256: `52180e202dd7ae578bb29cab0ea8766c3719771e6dd7a91bf84a4d9eeb0f088f`

This is a development package, not a signed/notarized distribution release. Windows manifest source/XML behavior is verified; Windows and Linux native runtime builds remain unverified. No existing profile or installed browser was modified. The test mounts were detached. Source-input hashes and bundle metadata are refreshed in `final-input-hashes.json` and `artifacts.json`.
