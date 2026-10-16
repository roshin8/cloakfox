# Chromium macOS checkpoint host identity implementation plan

> Execute inline with superpowers:executing-plans. The user authorized implementation, tests, commit and push without plan approval. Keep the current build running; macOS CI only.

**Goal:** Resume same-run Chromium objects on standard hosted Macs when the actual build inputs match, even if GitHub assigns different image revisions.

**Architecture:** Retain exact commit, root, source/patch/SDK locks, Python version/executable and selected Xcode/SDK links. Replace the broad image revision comparison with content fingerprints of the selected Xcode app (SDKs/toolchains/frameworks/tools), Python runtime source/binaries and installed Homebrew build tools plus their runtime dependency union. Match exact macOS product/build and architecture. Store image revision as provenance outside compatibility identity. Old checkpoints cannot be upgraded without the new content evidence. Publish small old/current receipts independently from large archives and report differing identity fields before extraction.

**Tech stack:** Python stdlib, existing tar/SHA verification, GitHub Actions standard macOS arm64 runners.

**Ruling:** Image revision previously served as a conservative proxy, but the hosted label assigned different revisions to consecutive jobs. Comparing actual host contents replaces that proxy; version labels alone are insufficient. Python import caches are excluded from its source/binary content fingerprint because imports regenerate them; `.py` and native library bytes remain bound. No source or object timestamps are changed by this policy. Existing archive extraction, SDK link validation, reserve and final runtime gates remain mandatory.

- [x] Recover actual checkpoint receipt using bounded ZIP64 HTTP ranges; confirm saved archive and runner-image mismatch evidence.
- [x] Regress same-version/same-size/same-mtime SDK mutation and host link/mode changes with real files; implement deterministic content fingerprinting.
- [x] Separate provenance from compatibility, keep legacy identity strict, and add pre-extraction field diagnostics.
- [x] Pin source job Python 3.12.10 explicitly and publish small receipts with always-uploaded evidence.
- [x] Verify actual Ninja/object reuse across fixture handoff and changed host rejection; full CI helpers, workflow lint and independent review.
- [ ] Commit/push explicit CI files, confirm current job remains untouched and successor queues. Hosted content identity, reuse, capacity, completed source SDK and strict browser runtime remain pending until their reports exist.


Review rulings: Homebrew INSTALL_RECEIPT.json and .brew recipe metadata do not
participate in compatibility; receipts remain provenance. Python external Mach-O
libraries are followed through explicit load commands and inherited LC_RPATH;
missing/ambiguous non-system inputs reject. Actual native linker fixtures verify
this path. Runtime helper unit tests retain stdlib-only requirements; the real
Ninja/Clang fixture runs as a required Mac step after tools are installed.
