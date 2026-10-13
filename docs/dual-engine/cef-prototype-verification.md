# CEF companion prototype verification — 2026-10-13

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
