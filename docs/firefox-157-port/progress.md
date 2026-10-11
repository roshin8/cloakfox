# Firefox 157 port progress

- Branch: codex/firefox-157-port; isolated managed worktree.
- 155 dirty-source snapshot: be1ce21cd5, 3,086 hashed files. No profiles copied.
- 146 reconciliation captured 109 files; current UI and live Math reconciliation still unfinished. 155 letterboxing patch retained because most conflicts were version adaptation.
- Source archive: official 157.0.1 SHA-512 manifest matched.
- First combined stack: 104 patches; 84 apply, 20 fail. Failures are recorded in initial-stack/results.json and per-patch logs. This is the red integration baseline; build has not started.
- Baseline Node attempt was invalid: native-source-dependent tests ran before source staging/patching. Do not count it as a product regression or pass.
- Storage cleanup authorized by user: reclaimed 25.3 GB, kept source work, profiles and current 146/155 builds. Ledger: storage-cleanup.json.

Next: repair patch application against fresh 157 pre-patch snapshots, reconcile Settings/Math without dropping 155 privacy behavior, run source/unit tests, configure/build and verify runtime.

- Superseded 146 worker-config-cache patch archived outside patch stack: 155 privacy completion already implements main-thread authoritative reads, mutex-protected worker snapshots, and stale-value eviction; retaining the older replacement would regress live observers. Active stack now 103 patches.
- Superseded locale-tag patch archived: 155 native realm locale implementation already preserves parsed subtags and process-neutral ICU defaults, eliminating the obsolete global pointer override. Active stack now 102 patches.

## Current verification

- Active 102-patch stack applies after repairing the HTTP/3 checksum hunk and screen-construction adaptation during pristine-target replay. Final one-shot clean replay remains required after compile repairs.
- Configure passes using existing Mozilla clang and cbindgen 0.29.4 (local-build.mozconfig).
- Node: 216/216 pass before the extra site-HMAC cache assertion; rerun pending.
- Python source harness: 10/10 pass, including private-field session-store adaptation.
- Settings reconciled additively: retain 155 sidebar, preview identities and modular privacy/network/workspace controls; restore 146 presets, application appearance, hardware-family sampling and native screen compatibility settings. Live UI verification remains pending.
- Native compile began. Restored 560 legitimate Cargo.toml.orig files removed during source staging. 303 manifest entries are absent from the official archive and require distinction from altered files if Cargo requests them. Full existing-file checksum scan finds upstream vendoring changes; no checks disabled.
- Native worker Math preserves 155 per-site derivation and live updates, but repeated derivation cost still requires caching before runtime acceptance.

Next: resolve compile errors, preserve worker Math performance, final fresh replay, live disposable-profile regression probes and app/DMG packaging.

- Independent pristine-target replay: all 102 patches passed; no skipped/rejected hunks; zero hash drift against the active tree. Evidence: check-results.json and check.log.
- Current Node suite: 217/217 pass. Python source/cache harnesses: 11/11 pass.
- Worker/window Math now cache site derivation; native cache regression covers 10,000 repeated calls plus regeneration, removal, site and container transitions.
- First compile exposed EventTarget GetOwnerGlobal removal; owning patches now use GetRelevantGlobal. Rebuild pending Rust compilation finishing.

- Captured 155 baseline rerun: 193 Node tests and 10 Python native/source tests pass. Current 157 suite adds 24 Node cases and the worker-site-cache native regression.
