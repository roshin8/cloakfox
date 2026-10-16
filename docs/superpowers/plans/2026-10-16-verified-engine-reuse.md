# Verified macOS engine reuse implementation plan

**Goal:** Reuse completed Chromium SDKs and Gecko packages when their committed build inputs match; rebuild current Chromium clients and rerun all current browser gates. Free standard hosted macOS only. Preserve the running workflow and all dirty implementation.

**Architecture:** Reusable engine workflows resolve immutable Actions artifacts by a versioned content key. On a miss they run the existing build. A source SDK is distinct from a Chromium client: only the SDK is reused. Gecko reuse is conservative: its key includes additions, extension, configuration and all packaging inputs; changing bundled Gecko assets still rebuilds the package. These are package inputs, not test coverage exemptions. No proprietary distribution or remote compilation service.

**Files:** scripts/ci/engine_artifact.py owns keys, trusted artifact lookup and sealed file integrity. chromium_source.py produces SDK/source receipt rather than clients; chromium_clients.py builds current patched/control clients and binds engine producer + consumer commits. chromium-engine.yml resolves/builds SDK; gecko-engine.yml resolves/builds package/native fixtures. chromium.yml and build-macos.yml retain current runtime/release gates. Native input restore verifies original producer commit; current consumer evidence binds that commit to exact current inputs.

## Constraints and policy

- Content keys are hashes of committed Git tree modes/object IDs and a format/platform/kind identifier. Dirty working files must not silently enter a key or a CI commit.
- Chromium keys cover source/CEF/toolchain pins, all native patch locks and bytes, apply scripts, source/checkpoint/host identity recipes and engine workflow. They exclude client/UI sources and tests. Current clients are always compiled/tested anew.
- Gecko keys conservatively cover Makefile, upstream pins, patches, additions, settings, branding, build scripts and its engine workflow. Bundled extension changes therefore invalidate reuse until a separately verified repackaging path exists.
- Resolve exact artifact names only. Trusted producer must belong to this repository, originate in push/manual on main or codex/firefox-158-port, and use the expected build/engine workflow. Artifact producer SHA/run and immutable artifact metadata bind the downloaded manifest; relevant producer completion gate must pass.
- Reject expired/missing artifacts (cold build), wrong platform/key/run/SHA, extra/missing files, changed hashes or links. No arbitrary origin/run input or PR-uploaded artifact accepted.
- Chromium SDK archive checksum and source/SDK hash must match before building; current embedded hash joins the original source/SDK values and current app receipt. Current app archive must still match current checkout commit.
- Gecko package and native fixtures are reused together under one verified manifest. Native fixture's original gitSha stays unchanged; runtime uses the verified producer SHA, while reuse evidence records current consumer SHA/key.
- Every current runtime privacy/library/Metal/transport/isolation/coexistence gate remains required. Engine reuse is not a green runtime result. No allowances.
- Artifacts expire after seven days and trigger a rebuild when absent. No cache/object deletion. Cold builds remain slow; no paid runners.
- Keep original macOS concurrency group and cancel-in-progress:false. No cancel or manual duplicate dispatch.

## Implementation tasks

1. [x] Add failing key/integrity/trust regression tests using real Git/tar fixtures; implement engine_artifact.py. Verify app changes preserve Chromium key, native changes invalidate it, Gecko bundled assets invalidate, and corrupt/untrusted payloads reject.
2. [x] Split SDK/source production from current client build; retain source/SDK/embedded validation and strict extraction. Test reusable SDK receipts plus current commit binding and tamper rejection.
3. [x] Move cold Chromium chain into reusable/manual engine workflow with lookup and success-gated outputs; add current client build before unchanged runtime. Move Gecko build/GPU jobs into analogous reusable workflow, publish same-run runtime artifacts after verification.
4. [x] Add scheduling/gate tests and actionlint; run CI helper suite with only fixture capacity simulated as previously documented. Independently review full changes, address findings, explicit-file commit/push and verify active run preserved + successor pending.

## Verification ledger

Implemented key/integrity/trust fixtures, SDK/current-client split, and both reusable native workflows. Review fixes: exact artifact-ID download layout, bundled fonts, engine-specific success gates, and current source-test invalidation. Keys establish committed source/recipe equivalence; producer host toolchains are retained as provenance rather than matched against the consuming runner. 62 CI helper tests pass with the documented small-fixture capacity simulation; eight affected/reusable/platform workflows pass actionlint. Independent reviewer ran 16 focused checks and found no remaining blockers after fixes. Real GitHub artifact API lookups returned expected cold misses. Hosted cold completion, reuse hit, and end-to-end browser runtime remain unproven until actual reports exist.
