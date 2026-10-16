# GitHub Actions: Gecko and Chromium

The `Build Cloakfox` workflow builds Gecko 158 for macOS arm64 and Linux x64, calls the reusable `Chromium source and runtime` workflow, and runs same-run concurrent Gecko/Chromium checks. It runs for pull requests, pushes to main and codex/firefox-158-port, version tags and manual dispatch. Chromium currently supports macOS arm64 only.

## Hosted storage evidence

[Initial survey](https://github.com/roshin8/cloakfox/actions/runs/38836571176) executed an actual Metal shader/compute check on standard hosted macos-26 and xcode-27 runners. Both passed. macos-26 selected Xcode26.6/macOS SDK26.5 and initially had approximately95.6GiB free.

[Unused-Xcode cleanup survey](https://github.com/roshin8/cloakfox/actions/runs/38836760626) measured approximately122.0GiB free on macos-26 afterward, with Metal still passing. The xcode-27 image had only45.6GiB afterward and is not selected for source builds.

The source workflow additionally removes unused mobile target platforms and simulator data, only on disposable GitHub-hosted Macs. Its first assessment measured **157.0GiB free** (168,607,563,776bytes), with Xcode26.6/SDK26.5 and actual Metal compute still passing; see [capacity evidence](ci-20261015/capacity-provenance.json). The superseded run was cancelled for a test-placement fix, so that result establishes capacity preflight, not full compilation. It preserves the selected Xcode toolchain and MacOSX.platform. It requires at least128GiB free, arm64, full Xcode, SDK26.5+ and actual Metal execution before downloading source. Its own build stages monitor a10GiB reserve. Before/after capacity reports, per-stage minimum-free samples and build logs are uploaded even on failure. These preflights are budgets; only a completed full build demonstrates capacity for that build.

## What each gate exercises

- Gecko: existing native build/package and Selenium fingerprint probes on macOS/Linux. Browser-dependent Python test outcomes now join the final failure gate. Unit tests also block draft releases. Node tests referencing firefox-src run after patch application in each Gecko build job, rather than attempting to read an absent source tree in the fast unit job.
- Chromium source: pinned source archive size/SHA256, pinned full CEF history and depot_tools revision, official CEF patches, RNG startup repair and ordered Cloakfox native patch locks. The uncommitted identity increment is not part of remote CI until its files are committed; once present the same builder adds and verifies that final patch.
- Chromium packaging: distribution templates supply build scaffolding only. Headers/wrapper come from matching generated/source files and CEF distribution transfer mappings. The framework must have identical source-output, SDK and app-embedded SHA256. The original binary SDK builds a separate negative control.
- Chromium runtime: fresh hosted Mac, verified same-commit archive and framework, actual Metal, complete engine suite with both clients, sandbox/storage isolation and owned TCP/QUIC certificate-rejection tests. Native classes skipping for absent binaries cause failure; CLT-only characterization and source replay are explicitly excluded from this binary-only runner.
- Coexistence: downloads the Gecko DMG and Chromium apps from this exact workflow run, verifies Chromium provenance, then exercises concurrent Gecko158/Chromium containers/personas/storage and pixel privacy. It never uses an installed /Applications browser.
- Release: draft Gecko artifacts remain the release format. Draft creation requires both builds, both Gecko runtime jobs, unit tests, Chromium source/runtime and coexistence. Test controls and evidence are retained as CI artifacts, not attached as browser downloads.

No paid or self-hosted runner is required by this configuration. Hosted job time is bounded below GitHub's six-hour maximum. A cold Chromium run exceeding that bound fails visibly; cached or faster build capacity must then be evaluated rather than reporting success.

## Current verification

Seven CI helper tests and actionlint pass locally. The packaging regression for transferred Chromium headers is covered by a failing-then-passing fixture. The full new hosted source build and runtime sequence still need their first successful run; hardware/capacity surveys alone do not establish that result. The ongoing local identity source build is independent and unchanged.

[Corrected full run](https://github.com/roshin8/cloakfox/actions/runs/38838708458) builds commit1288a030a7. Its hosted unit-test job passed; full builds and runtime completion are pending. The existing periodic build watcher now also checks the latest non-cancelled dual-engine CI run and fixes failures within this scope.
