# Versioned SDK client CI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the matching client and require all runtime checks using the uploaded locale SDK.
**Architecture:** One committed SDK lock pins archive and manifest assets, content hashes, and client source. One client-validation workflow consumes it, builds clients and runs independent required gates. Chromium source compilation remains an explicit separate workflow with no fallback from client CI.
**Tech Stack:** GitHub Actions standard macos-26, Python 3.12, CMake/Ninja client builds.
**Spec:** User instruction in this chat: finish SDK upload, pin matching client, run required checks on free runners; preserve everything, no Chromium rebuild or local native builds.

## Global Constraints

Preserve all checkpoint/release/artifact bytes. No local native build or execution. No paid runner. No privacy, Metal, sandbox, transport, fingerprint or coexistence waivers. No unrelated WIP staged/pushed. Import origin remains explicitly local, not hosted source-built.

## Review Focus

- Wrong/replaced SDK or manifest must fail before extraction/build.
- Archive traversal, symlinks, file sets and modes must be validated.
- Client must use the matching patch chain and source revision.
- Failed runtime gate must not skip independent remaining gates.
- Missing or mismatched Gecko provenance must fail coexistence.

## Tasks

- [x] 1. Verify upload assets and add SDK lock plus data-only verifier tests (tampering, source mismatch, unsafe archive), observe failure then implement verifier. Verify real archive without launching binaries.
- [x] 2. Replace existing SDK validation workflow with one lock-driven download/build/check job; retain reusable entry and separate source build. Carry the already verified probe-only media fixture as an explicit hashed client patch. Preserve apps before runtime tests and all diagnostics afterward.
- [ ] 3. Lint, run focused non-native tests, obtain independent review, publish only owned CI files against actual remote parent, dispatch once and verify hosted checks. Record results and update existing monitor.

## Execution ledger

Ruling: user explicitly authorized execution of this design; no additional design approval needed. Source checkout stays a06a951; the proven probe-only synthetic media device patch is recorded separately and never grants permissions. Local archive extraction/hash verification is data-only, not a native build.

Verification: seven verifier tests observed failing without implementation, then all seven passed. Workflow actionlint passed. Real archive preflight detected AppleDouble sidecars; creating a separate portable archive with COPYFILE_DISABLE=1 and --no-xattrs, retaining original upload.

Verification: portable archive all 1235 entries match exactly; preserved read-only mode using data_filter plus low-nine permission bits (new regression RED then GREEN). Eight verifier tests PASS, actionlint PASS, independent review no blockers. Both original and portable release assets retained.
