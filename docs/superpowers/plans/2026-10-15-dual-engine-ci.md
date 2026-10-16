# Dual-engine GitHub Actions implementation plan

> Execute inline with superpowers:executing-plans. No user plan approval is required.

Goal: build Gecko 158 on macOS arm64/Linux x64, build pinned Chromium/CEF from source on macOS arm64, and test both engines plus coexistence from the same checkout.

Architecture: retain the existing Gecko jobs; add a reusable hosted Mac Chromium build/runtime workflow and a same-run coexistence job. Use separate runners for Gecko and Chromium so their source/object trees never compete for disk. Upload provenance, capacity reports and test logs, with hard failure gates.

Constraints: preserve the running local identity build, its sources and SDKs. CI uses a fresh RUNNER_TEMP tree, real Xcode, native sandbox and Metal. No paid runner or external host. Source pin and ordered native patch hashes must match; no downloaded binary SDK may masquerade as a patched source build. The identity increment remains pending local verification and is included by CI only once committed.

- [x] Task 1: Add hosted-only storage preparation and pinned source bootstrap/build/SDK packaging helpers. Test deletion guard, active Xcode preservation, archive/hash validation, prerequisite hashes and generated/source/embedded framework provenance. Keep a minimum 10 GiB reserve while controlled CI processes run.
- [x] Task 2: Add reusable Chromium source-build + native/runtime workflow; connect existing Gecko jobs, strict engine tests, real Metal, isolation, TCP/QUIC and same-run coexistence. Ensure skipped native tests and browser-dependent Gecko test failures cannot yield a green gate. Keep release uploads limited to intended artifacts.
- [ ] Task 3: Validate helpers, YAML/actionlint and focused review; push and dispatch both builds on this branch. Inspect capacity after cleanup and preparation, actual runtime reports, source/SDK/embedded framework hashes. Fix observed CI failures without disturbing the local pipeline. Record observed results and remaining running stages accurately.

Review focus: cleanup outside hosted runners must refuse; active Xcode and macOS tools must survive; source/patch drift must fail before compilation; artifacts must belong to this run/commit; missing binaries/skipped runtime classes must fail the runtime job.

Review ledger: fixed transferred-header SDK refresh before ordinary lookup and preserved generated TRANSFER-README.txt; regression test failed then passed. No deferred review findings. Task3 hosted execution remains pending.

Hosted execution findings: source-dependent Node tests moved to prepared-source build jobs. Network unit job now installs pinned aioquic/h2 dependencies; wildcard harness reads the actual patched Gecko method rather than assuming its signature remains in diff context. Thirteen network tests and33 source-dependent Node tests pass locally; helper7/7 and actionlint pass. Hosted capacity157.0GiB, SDK26.5 and Metal verified; full compilation/runtime remain running.
