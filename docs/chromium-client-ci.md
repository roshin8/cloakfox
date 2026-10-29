# Chromium client CI

The normal validation path consumes a versioned binary SDK. It does not compile Chromium.

`engines/chromium/sdk-lock.json` pins the SDK release asset IDs and SHA-256 digests, the framework digest, the matching client revision, and its engine patch chain. `chromium-sdk-validation.yml` downloads and verifies those inputs, builds the client and an upstream negative control, saves the apps, and runs the required checks on a standard `macos-26` GitHub-hosted runner.

Current version: `locale-f03b85fd-20261029`, client source `a06a95168d462024d274570ab73f5b8c535ca103`. This SDK was compiled locally before import. Its provenance says so; importing it does not turn it into a hosted source build. It contains the locale/display/owned-IME patch chain. It does not include later regional-validation engine changes. The small hashed client patch provides a synthetic media device only in explicit probe/test-keychain mode, letting the actual deny callback execute on camera-less runners. It never grants media permission.

The draft release is a validation input, not a release-ready browser. Previously recorded local owned-IME password metadata and privacy inventory failures remain listed in the SDK manifest. Every hosted gate still runs and must pass. The retained Gecko app is verified against its own producer inputs for coexistence; this does not waive its separate historical release-test failures.

## Running validation

On the CI branch, use the existing entry point:

```sh
gh workflow run runner-survey.yml --ref codex/chromium-intel-build -f chromium_sdk_validate=true
```

The reusable `chromium-sdk-validation.yml` also has a direct manual entry once registered by GitHub. The old survey/recovery workflows remain available for historical recovery; they are not dependencies of client validation. The Chromium source workflow is separate and opt-in. A missing or incompatible SDK fails the client job; it never triggers an engine rebuild.

## Updating inputs

For client changes compatible with this SDK, pin a reviewed client commit in the lock. This first imported manifest deliberately binds its original source revision too: a future compatible client update must introduce an explicit reviewed compatibility rule instead of silently changing the pin. When native engine patches or the native API change, produce a new SDK version, retain the old one, and update the SDK lock and matching client together. Do not package an old compiled engine under a new source identity.

SDK publication happens once per engine version. Normal client builds download it; they do not require a fresh upload from a developer's mounted volume. Promoting this branch's workflow into the main PR pipeline is a separate reviewed change, not a merge of the unrelated development work in this checkout.

The workflow preserves built apps before runtime checks, and uploads evidence even on failure. Required checks cover C++ tests, actual Metal, upstream fingerprint libraries, the complete matching engine/privacy suite with unpatched control, sandbox/storage, TCP/QUIC/TLS certificate rejection, and dual-engine coexistence. Independent checks continue after another check fails; the job stays failed.
