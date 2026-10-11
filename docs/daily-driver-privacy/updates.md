# Release authenticity and automatic update readiness

Status, 2026-09-07: **offline artifact verification implemented; automatic browser
updates remain unavailable.** No production signing identity, MAR trust root,
owner update endpoint, notarization, or Windows signing service was configured.
Nothing was published and the updater remains disabled.

## Current implementation

`scripts/release_manifest.py` creates unsigned versioned JSON metadata for one
final package, or verifies its detached signature and the package. Python's
standard library handles JSON and SHA-256; the installed OpenSSL CLI performs
signature verification. There is no Python crypto dependency, key generator,
network request, installer, extraction, or modification of browser preferences.
Use a reviewed owner-managed RSA public key (2048 bits or stronger, preferably
3072+) with SHA-256; signing happens separately under the owner's key policy.
The tool never needs the private key. This detached signature is **not a MAR
signature, Apple Developer ID signature, or Windows Authenticode signature**.

The signed bytes bind product, version, release sequence, channel, platform,
filename, byte size, SHA-256, issue time and expiry. Verification authenticates
the raw manifest bytes before parsing them, rejects duplicate/unknown fields,
checks the expected channel/platform and supplied minimum sequence, then hashes
the local package. Manifest lifetimes are at most 30 days. Timestamps are Unix
seconds; an incorrect local clock can reject a good release or admit an expired
one. A newer signed release can exist even while an older manifest is unexpired.
Expiry alone does not establish that an artifact is the newest release.

The public key must arrive through an independently trusted channel or be pinned
in a trusted installation. Downloading a key alongside the artifact from the
same untrusted location authenticates nothing. Missing/invalid public keys and
signature verification failures cause nonzero exit; there is no unsigned bypass.

The required `--minimum-sequence` is an externally trusted floor. **This tool does
not persist or protect monotonic state.** Passing a stale floor allows replay of
an older, still-valid signed release. The release authority must allocate
increasing sequences per channel/platform and map versions correctly; semantic
version ordering is not inferred. A future installer must retain its last
accepted sequence in protected state and compare against the installed build.
Same-sequence verification is allowed for repeated artifact checks.

Only plain artifact basenames are accepted; metadata cannot choose a path. The
caller supplies the package path explicitly. Package/key/manifest/signature
symlinks and nonregular files are rejected; metadata and signatures have 64 KiB
limits. OpenSSL receives snapshots of the key, signature, and exact manifest
bytes. On platforms with `O_NOFOLLOW`, opening also rejects a swapped symlink.
Use a trusted local directory: ancestor symlinks, concurrent local writers, and
post-verification replacement of the package are outside this offline check's
protection. Verification is a statement about bytes read at that time. A future
installer must operate on the same verified immutable artifact/handle and must
not extract or execute anything before successful verification.

## Manual release workflow

Package signing/notarization must finish before generating the manifest; any
later modification invalidates the digest. These commands are templates for an
owner with real signing configuration; they were not run with production keys.
The output manifest must not exist (creation refuses to overwrite it).

```sh
python3 scripts/release_manifest.py create \
  --package dist/Cloakfox-macos-arm64.dmg \
  --output dist/Cloakfox-macos-arm64.release.json \
  --version "$RELEASE_VERSION" --sequence "$RELEASE_SEQUENCE" \
  --platform macos-arm64 --channel release --expires-at "$RELEASE_EXPIRES_AT"

# Run only in the owner's protected signing environment, or use its equivalent
# HSM/signing-service operation over these exact bytes. No key enters build PRs.
openssl dgst -sha256 -sign "$OWNER_SIGNING_KEY" \
  -out dist/Cloakfox-macos-arm64.release.sig \
  dist/Cloakfox-macos-arm64.release.json

python3 scripts/release_manifest.py verify \
  --manifest dist/Cloakfox-macos-arm64.release.json \
  --signature dist/Cloakfox-macos-arm64.release.sig \
  --package dist/Cloakfox-macos-arm64.dmg \
  --public-key "$TRUSTED_OWNER_PUBLIC_KEY" \
  --platform macos-arm64 --channel release \
  --minimum-sequence "$TRUSTED_MINIMUM_SEQUENCE"
```

Distribute the package, JSON and signature together only after verification.
Distribute/pin the public key independently. Prefer a mature framework such as
TUF when implementing durable trust-root rotation, delegated signing and rollback
state; do not expand this small manual checker into a homegrown update protocol.
Compromise recovery must use a separately trusted owner channel, not a blanket
signature/sequence bypass in this script.

## Safe CI integration

The existing build workflow only uploads package artifacts. Its macOS package
step uses `codesign --sign -` (ad-hoc identity). That proves neither publisher
identity nor notarization. An ordinary PR job must never receive release keys.
The safe immediate integration in `.github/workflows/build.yml` is this step
inside `unit-tests`, after Python setup:

```yaml
      - name: Test offline release authenticity checks
        run: python3 -m unittest discover -s tests/release -v
```

This tests disposable test-only keys created in temporary directories and deleted
at cleanup. It generates no production trust material. Python and OpenSSL must
be present; missing OpenSSL fails rather than silently skipping the tests.

A future protected release job should download immutable package artifacts from
a reviewed build, finalize platform signatures/notarization, call `create`, send
the exact manifest to the owner's signing service, call `verify` using a pinned
key and externally allocated sequence, and upload all three artifacts. Require
all expected platforms and verify the actual contents/version before signing:
this script signs declared metadata, not the correctness of an embedded browser.
Do not append a pretend signing step with nonexistent secrets to the current
workflow. No change to `assets/base.mozconfig` is appropriate at this stage.

## Native Firefox update requirements

Firefox's updater consumes MAR archives and update-service XML, not a DMG/ZIP
and this JSON. The local Firefox 155 source confirms:

- `toolkit/mozapps/update/updater/moz.build` selects embedded primary/secondary
  DER certificates according to `MOZ_UPDATE_CHANNEL`. A new unrecognized channel
  falls back to dependency test certificates! Replace this selection through a
  maintained Cloakfox patch with owner-controlled production certificates;
  merely changing the channel name is not sufficient.
- `updater.cpp` verifies MAR signatures under `MOZ_VERIFY_MAR_SIGNATURE` and reads
  `ACCEPTED_MAR_CHANNEL_IDS` from `update-settings.ini`. Build/channel values,
  signed MAR product information and acceptance policy must agree.
- `tools/update-packaging/make_full_update.sh` and incremental packaging tools
  create MARs. Mozilla's `signmar`/NSS tooling provides the signature format and
  verification; do not replace it with the detached JSON signature above.

Mozilla documents [MAR files and signmar](https://firefox-source-docs.mozilla.org/toolkit/mozapps/update/docs/MarFiles.html)
and the [in-app update process](https://firefox-source-docs.mozilla.org/toolkit/mozapps/update/docs/InAppUpdateProcess.html).
An owner must supply HTTPS update metadata/package endpoints, product/channel
routing, staged rollout policy, freshness/security rebase monitoring, release
signing service and key rotation. Test-server documentation includes developer
shortcuts; production must retain MAR verification and must never use
`--enable-unverified-updates`.

Platform signing remains separate: final application internals and the resulting
MAR must follow the correct signing order described in Mozilla's
[signing pipeline](https://firefox-source-docs.mozilla.org/taskcluster/signing.html).
macOS elevated updates and Windows maintenance service each have additional
platform trust checks; owner identities must be integrated and exercised instead
of relying on Mozilla's signing identity or test certificates.

Before enabling the updater, demonstrate on every supported platform:

1. A real owner-signed complete MAR upgrades an installed previous release;
   partial MAR and complete fallback produce the same files as a fresh install.
2. Wrong signer, changed MAR, wrong channel/product, older version/build and
   stale metadata fail safely; test key rotation and offline/expired services.
3. Interrupted download/apply, low disk space, insufficient permissions and
   damaged partial updates recover without profile loss or a broken install.
4. Final platform signature/notarization verification succeeds after applying the
   update; Windows maintenance service and macOS elevated cases are covered.
5. UI clearly reports installed version/build age, pending/failed updates and
   update availability, including the current lack of automatic updates.

Use Mozilla's [update verification suite](https://firefox-source-docs.mozilla.org/tools/update-verify/index.html)
for installed-file equivalence. No native update application/recovery or platform
release signing test was run in this task. The manifest suite's passing checks
must not be reported as completion of automatic security-update delivery.

## Checked evidence

`python3 -m unittest discover -s tests/release -v` passes 11 tests: valid signature,
tampered package/metadata/signature, missing/wrong owner key, wrong channel/platform,
sequence below floor, expired/future/malformed signed fields, path traversal,
package symlink, duplicate JSON fields and prevention of manifest overwrite.
Tests failed first when the CLI was absent, then passed against real OpenSSL.
No browser/build tools, downloads, installer, account changes or global installs
were needed for these checks.
