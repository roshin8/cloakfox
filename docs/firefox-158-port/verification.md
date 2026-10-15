# Firefox 158 port verification

Branch: `codex/firefox-158-port`. Version: **158.0-beta.26**, macOS arm64. BuildID: **20261014202151**.

The complete current 157 source snapshot, including uncommitted privacy repairs, was preserved in a separate managed worktree. The installed 157 app and existing profiles were not changed. The installed app was subsequently replaced with the verified 158 package; profiles were left unchanged. The user authorized committing/pushing the port and retiring superseded 157 privacy branches/worktree.

## Source and build

- Official Mozilla 158.0 source SHA256: `fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb`.
- Original 157 baseline: 333 native patch targets compared against the preserved checkout, zero drift.
- Fresh 158 replay: 128 patches; 297 pristine targets; 335 resulting target/staging hashes; zero offsets, fuzz or drift. See `final-replay.json` and `replay-final.log`.
- Full native build succeeded (`build-4.log`). LLVM 19.1.7, Rust 1.94.1, cbindgen 0.29.4, macOS SDK 26.5; configuration in `build-environment.json`.
- Initial attempts exposed SDK/toolchain incompatibilities and missing DOM namespace qualifications; repaired before the successful full build. The build reports 933 compiler warnings, including upstream availability, deprecation and unused-code diagnostics; these were not exhaustively classified. No claim of warning-free compilation.

## Regression results

| Check | Result |
| --- | --- |
| Node unit tests | 242 passed, zero skipped/failed |
| Binary-enabled Python tests | 39 passed, one conditional Firefox-UA Sec-CH-UA skip |
| Browser runtime probes | 113/113 passed after three explicit reruns |
| Additional desktop/headful probes | 5/5 passed after isolated cursor rerun |
| Network reference units | 13 passed |
| Blocker units | 6 passed |
| Release units | 28 passed |
| Build staging, icon, font rename, JS scoring checks | Passed |

Runtime coverage includes container/site identity isolation, startup and worker realms, fonts/canvas/WebGL/WebGPU, locale and navigation fields, consent and fake media, WebRTC/proxy routes, allowed WebSocket identity, TLS/H2/H3 wire fixtures, settings/persona persistence, pointer/focus/Monaco behavior and media recovery adapters. Independently measured stock Firefox 158 references retain certificate rejection checks. JPEG XL image/bitmap/canvas/PNG paths and CSS typed arithmetic are checked with protection enabled and disabled.

The initial runtime pass was 110/113. A missing local `websockets` dependency prevented one probe from running; installing it enabled the full background-activity probe. A new feature test incorrectly demanded exact DOMRect values despite existing geometry noise; corrected tests retain exact CSS/computed layout assertions, bounded protected geometry and explicit privacy configuration checks. A persona settings click failure did not reproduce with added failure diagnostics; subsequent headful repetition also passed. No production change was made to force that UI result.

The initial additional desktop cursor run was 142/145. Its three native-control samples showed missing top hover and trusted departures after menu entry. An isolated rerun passed 145/145. The transient cause remains unidentified and is not claimed fixed. The widget/APZ cursor suite also passed 145/145. Raw red/green artifacts remain under `tests/fingerprint/reports/158-port`.

The initial Python run exposed a C++ test stub missing the DOM namespace used by the extracted production method. Adding matching stub aliases left the production method and owner assertions unchanged; the fresh full run passed. The conditional Sec-CH-UA skip is covered separately by the passing explicit Chromium/Firefox user-agent runtime probe.

Source whitespace checking passes outside patch artifacts. A whole-diff whitespace check flags required blank context lines inside regenerated unified patches; their authoritative format/content validation is the successful strict replay, rather than deleting context whitespace.

## Review

Independent source review found and verified repairs for patch no-final-newline formatting (P1) and the feature-probe geometry expectation (P2). Final review found no remaining actionable issues in the reviewed port changes. See `code-review.md` for scope and evidence. This is not an exhaustive audit of all inherited 157 behavior.

## Package

Package creation succeeded. `package-identity.json` records DMG checksum, size and version. The app mounted from the DMG contains no external symlinks; executable and XUL Mach-O UUIDs match the tested development build. The first packaging harness attempt incorrectly expected the bare `158.0` app version; the actual intended version is `158.0-beta.26`. Correcting that assertion allowed package checks to run without changing the artifact. Representative packaged-app checks are recorded separately in `packaged-results.json`; all **12/12 passed**, using the app mounted directly from the DMG. These cover packaged resources, Firefox 158 native features, identifier/graphics/realm/language checks, WebSockets, TLS/HTTP and QUIC wire behavior, media permissions, the HackerRank media recovery adapter fixture and persona generation.

## Limits

Testing covers the available repository suite on macOS arm64, not every browser behavior. Linux/Windows builds, native real camera/microphone quality, macOS screen-recording approval, and a real HackerRank/Zoom call were not exercised. Media tests use local fixtures/fake capture; adapter tests do not prove compatibility with future website changes. The historical one-off `probe_font_spike.py` requires a separate experimental font input and is excluded by the suite's normal discovery. This local package is not a notarized production release.

## Publish and cleanup preparation

Before publishing, all 335 native hashes were rechecked with zero drift, Node tests were rerun, and binary-enabled Python tests were rerun against `/Applications/Cloakfox.app`. Their outputs are `precommit-node.log` and `precommit-pytest.log`. A fresh comparison confirmed all 3,679 preserved 157 source inputs remain unchanged in the old privacy checkout. Its reusable ALPS server fixture was copied into the 158 report fixture directory before worktree cleanup.

The directory named `firefox-157-port` currently holds the separately pushed `codex/dual-engine-prototype` branch and is intentionally preserved. It is not the superseded 157 privacy branch.
