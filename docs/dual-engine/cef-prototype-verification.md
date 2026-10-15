# CEF companion prototype verification — 2026-10-13

Latest source-built canvas increment: [runtime evidence](cef-canvas-privacy-20261015.json)
and [coverage/limitations](cef-canvas-privacy.md). The original binary SDK baseline
below is preserved; the new source-built companion has partial native canvas protection.

Branch: `codex/dual-engine-prototype`, based on Firefox 157 commit `24c23d478e`.
CEF: `154.0.34+g14c5a08+chromium-154.0.8037.98`, stable macOS arm64 distribution.
The archive matches its official index SHA1 and pinned SHA256 in `engines/chromium/cef-lock.json`.

## Implemented and measured

- Standalone C++/Cocoa Chromium companion with native Views navigation controls and sandbox-enabled helpers.
- Private parent-process pipe control; no listening port or web-to-host binding. Strict schema/field validation, increasing request IDs and launch-option whitelist.
- Separate persistent request contexts for containers 1 and 2; memory-only private context 3. Private contexts discarded after the last private window closes.
- Owned directory checks, symlink rejection, exclusive profile-root locking and immutable native/test keychain mode.
- Real cookies, localStorage, IndexedDB, CacheStorage and service worker isolation, including a process restart and private-window closure/reopen.
- Native Chromium navigator/appVersion and APIs; WebGL2 and WebGPU available on the test machine. No Firefox identity/API emulation.
- Actual macOS seatbelt enforcement: renderer cannot write to an existing repository file; browser-process positive control can. This was a policy query, not a write to that file.
- Camera/microphone and geolocation requests denied before hardware access.
- Intentional renderer crash leaves the companion alive and native navigation recovers.
- Real TCP/QUIC ClientHello and QUIC initial/transport parameters observed on owned fixtures. TCP offers H2; forced loopback QUIC offers H3. Neither completes authenticated HTTP because the untrusted test certificate is correctly rejected.
- Ordered quit during asynchronous profile creation, invalid URLs/versions/fields, replay and unsafe engine overrides checked at runtime.

Evidence: `cef-isolation.json`, `cef-transport.json`, `cef-protocol-checks.txt`,
`cef-cpp-checks.txt`. The transport evidence contains public protocol structure;
it excludes private keys, TLS randoms, traffic keys, cookies and user credentials.

Verification passed: one C++ boundary test, two extraction-recovery tests, seven native protocol/lifecycle tests,
the storage/sandbox/permissions runtime probe and the TCP/QUIC runtime probe.
The existing Node suite passed 234 tests; Python passed 19 with 16 historical
skips. The compiled bundle's manifest/helper checks are in `cef-build-artifact.json`.

## Scope and gates still open

This is a **partial milestone 1 prototype**, not a completed dual-engine browser.
It does not add Chromium to Gecko's settings/tab bar or implement native canvas
noise, Firefox privacy actors, generation options, site exceptions or privacy parity.
The capability report says `privacyPatched:false`; unsupported privacy fields are
rejected. The preliminary inventory covers 112 canonical Gecko patches, literal
optional/privacy preferences and 98 settings bindings; manual hook/worker audits remain.

Native fingerprint patching requires a source-built Chromium/CEF baseline.
Full Xcode is absent from the active developer directory. Internal APFS storage
has roughly 22 GiB free, below our 128 GiB source-build budget. The external USB
disk has space but is ExFAT; it would need an APFS build image or another supported
build volume. Read-only preflight reports capture these facts. No drive was
reformatted, no source checkout downloaded and no global developer directory changed.

Tests deliberately use `--test-keychain`; the test encryption key is not suitable
for real accounts or sensitive browsing. Real Keychain integration, downloads,
complete browser UI behavior/accessibility, authenticated H2/H3 SETTINGS, TLS
ticket/connection isolation, production Alt-Svc routing and worker fingerprint
patches remain unverified. CEF is a promising candidate; the final choice awaits
the native privacy patch and broader browser-feature checks.

## Gecko preservation

No Gecko product/source/settings files changed. The existing native owner/profile,
proxy and refusal runtime probe passed before prototype work. The Firefox DMG
SHA256 remains `1024cfb8e4b3b4e947b9e1266cab977d12f9623c6de53280fd6a35946234def2`.
The other agent's changes in the older checkout were not modified.

## Review and UI follow-up

Independent review found no confirmed critical/important issue in the initial
prototype and one minor incomplete-extraction recovery issue. Extraction now
stages the SDK and publishes it only after success; an existing unmarked tree is
preserved as `.incomplete`. Both failure and recovery paths passed local archive tests.

The initial visual check found missing toolbar attachment. Attaching CEF's Chrome
location bar then exposed a reproducible close-time native crash. The companion
now uses its own native Views text field and navigation buttons, without a Chrome
profile menu. Native protocol/lifecycle and isolation probes pass after this change.
AppKit crash-state restoration is suppressed through process-local registered
defaults because session restoration belongs to the controller; no global macOS
preference is changed. The Mac became locked during UI work, so final address-field
appearance, keyboard navigation and accessibility interaction remain unverified.

## Follow-up — 2026-10-15

The Mac is now available. A fresh native UI check against an owned loopback
fixture verified visible address entry and typed navigation, Back, Forward,
Reload (new server response) and window close. The preview launcher exited 0.
The native address field appears in the accessibility tree. Page-content
accessibility and keyboard shortcuts remain unverified.

Two new native popup characterization tests passed. Persistent popups share
only the opener's container storage, including after the opener closes. Private
popups share the opener's private context while any private window remains;
after the last private popup closes, reopening starts with empty storage.
A persistent window using the same numeric container ID retains separate data.
No production runtime code or binary changed in this follow-up.

Fresh verification: 11 Python engine tests and one C++ boundary test passed.
Earlier broader Gecko/network evidence above remains dated 2026-10-13 and was
not rerun for this test/documentation change. Current read-only source preflight
reports are `cef-source-preflight-internal-20261015.json` and
`cef-source-preflight-external-20261015.json`: macOS SDK 27.0, full Xcode absent,
internal free space below the 128 GiB budget, external ExFAT volume with capacity.
The native source patch and later integration milestones remain blocked/pending.

## Experimental CLT configuration — 2026-10-15

The earlier source preflight reports describe the standard upstream build path.
Full Xcode is not proven categorically necessary for a custom source build.
An opt-in, non-official Command Line Tools adaptation now exists for the pinned
Chromium mac_sdk.gni. The patch uses installed CLT receipt version 27.0 and real
SDK/compiler paths, without a fake Xcode bundle, xcodebuild wrapper, sign-in,
license acceptance or system settings changes.

The pinned-source patch and helper passed four focused tests. The real patched
mac_sdk.gni passed an isolated GN generation test with explicit minimal surrounding
imports; the default Xcode branch still fails on this CLT-only machine and CLT
mode rejects official builds. Native Cocoa/Metal code compiled and executed using
the paths produced by that GN branch. Evidence: `cef-clt-configuration-20261015.json`.
Legacy xcode_version fields in this development mode encode the actual CLT toolset
version; xcode_build explicitly identifies CLT. These are build compatibility
fields, not evidence of a full Xcode installation.

This is not a complete Chromium/CEF source build. The machine lacks ibtool,
actool, metal and momc; targets requiring those tools remain unsupported by this
adaptation. CEF nib-based sample applications explicitly use ibtool. Framework
resource dependencies and the complete build graph remain unverified, as do
native privacy patches. Available internal APFS space is still below the source
build budget. Current regression checks: 15 engine Python tests, one C++ boundary
test and 234 existing Gecko Node tests passed. No CEF browser binary or Gecko
product code was changed.

Focused review found two configuration regressions: the initial CLT branch did
not enforce mac_sdk_min and silently ignored mac_sdk_path overrides. Both were
reproduced as successful GN generations that should have failed, then repaired.
The final GN probe now verifies rejection of too-old SDKs and unsupported custom
SDK paths as well as official-build rejection and normal CLT configuration.

## Full source baseline — 2026-10-15

The pinned Chromium 154.0.8037.98 / CEF 154.0.34 framework and native sandbox
library now build from source with Apple CLT 27.0 and macOS SDK 27.0. The source
is internal and output is on an external APFS sparsebundle; no Xcode sign-in,
installation, global developer-directory change or drive reformat was used.
This is an experimental non-official build, rather than upstream Xcode support.

Build adaptations use Chromium's build-local SDK aliases and ANGLE's existing
runtime Metal shader compilation. The pinned CEF lazy-seed patch exposed an
allocator-critical first-use RNG allocation; the local macOS repair seeds its
128-bit state through getentropy without allocating. The source companion also
disables Chromium's development field-trial test cohorts, which requested
Aperitif helpers not shipped by the pinned CEF distribution. Normal feature
defaults, allocator checks and sandbox enforcement remain enabled.

The source-linked app passes 19 engine tests and one C++ test. Native probes
verify persistent/private storage and popup lifetime, restart isolation, malformed
input/replay rejection, renderer crash recovery, denied media/location access,
and actual macOS renderer seatbelt enforcement. WebGL2 shaders compile, draw a
triangle and read back [255, 0, 0, 255] through ANGLE Metal on Apple M2 Pro.
WebGPU API availability is observed; WebGPU workloads are not verified here.
Owned TCP/QUIC fixtures observe native ClientHellos and reject untrusted
certificates. Authenticated HTTP/2 and HTTP/3 SETTINGS, session tickets and
connection isolation remain unverified.

Fresh SHA256 verification matches the source output, packaged SDK and embedded
app framework: `544e6e78aba087413376f6e3954a96dc11b5317c24aaba54b8aa1db25e4a3056`.
The original binary-SDK companion remains unchanged. One cached object with an
invalid Mach-O header was preserved and rebuilt after a header audit of 38,517
outputs found exactly one invalid header; its origin is not established.

Evidence: [build/provenance](cef-source-build-20261015.json),
[isolation and graphics](cef-source-isolation-20261015.json),
[transport](cef-source-transport-20261015.json),
[engine tests](source-companion-units-20261015.txt),
[C++ test](source-companion-ctest-20261015.txt).
[Build instructions](cef-source-build.md) include the source archive pin and
standalone SDK transfer requirements. The tested app is
`/Volumes/CloakfoxChromiumBuild/source-build/source-companion-build/Release/CloakfoxChromium.app`.

Native Chromium privacy protections and the shared Gecko/Chromium UI remain
pending. This result completes the source-build baseline, not milestone 1's
native canvas privacy gate or privacy parity.
