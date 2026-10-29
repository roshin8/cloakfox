# Chromium client CI

The normal validation path consumes a versioned binary SDK. It does not compile Chromium. The existing `chromium.yml` entry point now calls SDK client validation instead of the engine builder. Its first gate refuses to test an old pinned client when the client/native/test inputs under review differ.

`engines/chromium/sdk-lock.json` pins the SDK release asset IDs and SHA-256 digests, the framework digest, the matching client revision, and its engine patch chain. `chromium-sdk-validation.yml` downloads and verifies those inputs, builds the client and an upstream negative control, saves the apps, and runs the required checks on a standard `macos-26` GitHub-hosted runner.

Current version: `locale-f03b85fd-20261029`, client source `a06a95168d462024d274570ab73f5b8c535ca103`. This SDK was compiled locally before import. Its provenance says so; importing it does not turn it into a hosted source build. It contains the locale/display/owned-IME patch chain. It does not include later regional-validation engine changes. The small hashed client patch provides a synthetic media device only in explicit probe/test-keychain mode, letting the actual deny callback execute on camera-less runners. It never grants media permission.

The SDK validation prerelease is a validation input, not a release-ready browser. Previously recorded local owned-IME password metadata and privacy inventory failures remain listed in the SDK manifest. Every hosted gate still runs and must pass. The retained Gecko app is verified against its own producer inputs for coexistence; this does not waive its separate historical release-test failures.

## Running validation

After merging, recheck the preserved SDK apps on main:

```sh
gh workflow run chromium-runtime-recovery.yml --ref main
```

To rebuild only the matching clients against the saved SDK, use `gh workflow run chromium-sdk-validation.yml --ref main`. The old survey/recovery workflows remain available for historical recovery; they are not dependencies of client validation. The Chromium source workflow is separate and opt-in. A missing or incompatible SDK fails the client job; it never triggers an engine rebuild.

## Updating inputs

For client changes compatible with this SDK, pin a reviewed client commit in the lock. The manifest retains its original `sdkSourceRevision`; the verifier compares committed native patch/recipe inputs between that revision and the new client revision. Client-only changes can reuse the SDK; added or changed native patches/recipes fail closed. Ordinary CI additionally checks that the code and tests under review match the client pin, so a frozen older snapshot cannot make unrelated changes appear green. When native engine patches or the native API change, produce a new SDK version, retain the old one, and update the SDK lock and matching client together. Do not package an old compiled engine under a new source identity.

SDK publication happens once per engine version. Normal client builds download it; they do not require a fresh upload from a developer's mounted volume. The CI integration preserves the newer application source and isolates the historical test fixtures from the current main test suite.

The workflow preserves built apps before runtime checks, and uploads evidence even on failure. Required checks cover C++ tests, actual Metal, upstream fingerprint libraries, the complete matching engine/privacy suite with unpatched control, sandbox/storage, TCP/QUIC/TLS certificate rejection, and dual-engine coexistence. Independent checks continue after another check fails; the job stays failed.

## Main compatibility boundary

Main currently includes native regional validation and newer client/shared-policy changes absent from this SDK. The ordinary current-client gate deliberately fails on those differences. Manual SDK validation/recheck workflows validate only the explicitly pinned a06a951 snapshot, not the current main application. A green current-main native gate requires a matching newer SDK; do not relax the guard or roll back main to get a green snapshot result. This integration does not rebuild Chromium or change the saved SDK/apps/checkpoints. Existing Actions artifacts retain their existing expiration dates.
