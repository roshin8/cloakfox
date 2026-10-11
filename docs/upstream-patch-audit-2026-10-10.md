# Firefox version and Camoufox patch review — 2026-10-10

## Build status

The separate Firefox 155 worktree uses **155.0.1-beta.25**. Its app bundle
responded successfully to `--version` during this review. Its executable and XUL
SHA-256 hashes match the recorded privacy-completion artifacts. The loose
`dist/bin/cloakfox --version` failed with “Couldn’t load XPCOM”; use the app bundle.
This is a startup/version check, not a fresh full browsing acceptance run.

Recorded macOS arm64 acceptance: native build, 183 Node tests, 22 browser probes,
83 applied patches and 198 matching source files. See
[completion report](../.worktrees/firefox-155-compat/docs/privacy-completion/README.md).
Automatic updates, Safe Browsing provider activation, owner signing/notarization,
and Windows/Linux acceptance remain unfinished. Recent active-checkout compatibility
changes must be reconciled before replacing the active build with this worktree.

Mozilla’s live [version feed](https://product-details.mozilla.org/1.0/firefox_versions.json)
reports stable **157.0.1**, beta **158.0b5**, and nightly **160.0a1**.
[157.0.1 release notes](https://www.firefox.com/en-US/firefox/157.0.1/releasenotes/)
include a security fix. Firefox 155.0.1 is therefore not the current stable baseline.

## Upstream source

Reviewed the original [daijro/camoufox repository](https://github.com/daijro/camoufox),
current fetched main snapshot `f008b768e258ab5a243b5ebd77393a679caaa89c`.
The snapshot’s commit date is October 11 (repository metadata), despite this
review’s local October 10 date. Its `browser/upstream.sh` targets Firefox
**156.0.1 / beta.32**; this describes source configuration, not proof of a published release.
Patches now live in `browser/patches/`. This review inventories 46 patch files,
compares filenames and inspects selected native changes against Cloakfox 155.
Different filenames alone are not evidence that functionality is missing.
The initial inventory preceded completion of the older September snapshot fetch.
The follow-up below now compares that exact snapshot with current source.

## Findings

| Upstream patch | Cloakfox 155 finding / follow-up |
|---|---|
| `windows-exe-manifest.patch` | Concrete candidate: current source contains `firefox.exe.manifest`, but no `cloakfox.exe.manifest`. Adapt the app-name manifest and verify Windows build resources/OS capability behavior. Not runtime verified on Windows. |
| `contentaccessible-parity.patch` | Concrete candidate: current source still conditionally packages crash-page resources and packages the development helper for nonofficial builds. Compare against matching stock Firefox first; adapt dependent startup call sites together. |
| `rust-vendor-unknown-fallback.patch` | Linux build candidate: resolves ambiguity among Rust target vendors. Confirm the toolchain reproduces the ambiguity before porting. |
| `user-agent-app-name.patch` | Already covered: applied `browser/moz.configure` sets `MOZ_APP_UA_NAME` to Firefox through the LibreWolf compile-time patch. |
| `window-setter-seal.patch` | Upstream Juggler lifecycle does not match Cloakfox. Cloakfox’s screen/navigator setter gates already require the privileged Shield caller, and WebRTC setters were hardened. Audit remaining gates rather than importing automation lifecycle code. |
| `media-device-spoofing.patch` | Same filename but substantially different behavior: upstream now routes configured devices through a fake media engine. Cloakfox’s older patch filters enumeration. Importing upstream wholesale could replace real camera/microphone capture; requires separate design and real-media acceptance. |
| `media-codec-spoofing.patch` | Upstream can report container/codec support despite absent decoders. Cloakfox already has codec/media-capability patches with different keys and behavior. Review consistency with actual playback before any adoption. |
| `popup-blocker-parity.patch`, `trusted-automation-events.patch`, `wheel-native-ticks.patch`, `debugger-invisible-to-content.patch` | Primarily automation/Juggler changes. No wholesale adoption for the daily-use browser. |
| `no-search-engines.patch`, `no-css-animations.patch`, `disable-extension-newtab.patch`, onboarding removal | Product choices conflict with or differ from daily-use goals; not missing fixes by default. |
| Font/system-ui/touch/voice/SessionStore fixes from the previous snapshot | Already adapted and verified in the [September hardening report](../.worktrees/firefox-155-compat/docs/daily-driver-privacy/camoufox-upstream-hardening.md). Newer changes to those files still require detailed diff/acceptance before claiming parity. |

No browser patches were applied, merged or rebuilt by this review.

## Follow-up: fingerprinting/privacy behavior comparison

Compared current `browser/patches` against exact prior upstream snapshot
`eb5dc3bc5b917d1e6c71d9cacfecdddb55fbfc4a` and against the maintained patches,
actors and applied native source in the Firefox 155 worktree. The old snapshot
is now available locally, so file moves were distinguished from behavior changes.
These are source findings, not newly reproduced browser failures. No patch was
applied and no browser regression suite was run for this follow-up.

### Additional fixes absent from the inspected Firefox 155 source

1. **WebGL state and context consistency — highest-confidence candidate.**
   Current upstream limits configurable `getParameter()` overrides to fixed device
   limits, preserves real mutable state, honors WebGL version/extension eligibility,
   treats null table entries as uncaptured rather than forcing null, and reports
   actual resolved context attributes. Cloakfox 155 still looks up the table
   unconditionally at `ClientWebGLContext.cpp:2281`, has an optional undefined-value
   blocking path and config-overridden context attributes around line 835.
   A configuration can therefore contradict state the page just changed or the
   context it actually obtained. Port as one behavior change; retain per-site and
   per-container configuration. Regression reference:
   [webgl-live-state.py](https://github.com/daijro/camoufox/blob/f008b768e258ab5a243b5ebd77393a679caaa89c/browser/tests/playwright/patches/webgl-live-state.py).

2. **Audio analyser noise accumulation — highest-confidence candidate.**
   Upstream applies frequency noise to a scratch copy of the smoothed output.
   Cloakfox 155 still modifies `mOutputBuffer` directly in both float and byte
   frequency reads (`AnalyserNode.cpp:239` and `:274`). That buffer is reused in
   subsequent FFT smoothing, so repeated reads can compound the perturbation.
   Adapt the copy behavior while keeping Cloakfox’s site-derived seed and privacy
   exception policy. Regression reference:
   [audio-frequency-noise.py](https://github.com/daijro/camoufox/blob/f008b768e258ab5a243b5ebd77393a679caaa89c/browser/tests/playwright/patches/audio-frequency-noise.py).

3. **Owner identity for detached documents — confirmed source difference, runtime test needed.**
   Upstream resolves context IDs from the node/document principal, including
   `createHTMLDocument()` and `DOMParser` documents with no browsing context.
   Cloakfox’s `ClientWebGLContext::GetUserContextId()` (`:800–819`) still looks for
   a browsing context and otherwise returns 0. The general implicit MaskConfig
   lookup can separately use the executing window, so this does not prove every
   detached-document query leaks or reads identity 0. Audit explicit manager paths
   and font ownership too; use two identities and detached-document controls.
   Reference:
   [webgl-renderer-pair.py](https://github.com/daijro/camoufox/blob/f008b768e258ab5a243b5ebd77393a679caaa89c/browser/tests/playwright/patches/webgl-renderer-pair.py).

4. **Speech backend failure handling — confirmed missing guard, platform-dependent.**
   Upstream `voice-spoofing.patch` ignores host speech-backend errors while a
   configured voice list is active. Cloakfox’s `nsSynthVoiceRegistry::NotifyVoicesError()`
   (`:396`) still forwards them. This can make configured voices report a failure
   belonging to the real host backend. Reproduce with a configured voice list and
   missing/failing backend, especially Linux. The earlier native-voice registration
   suppression is already adapted; this is a different guard.

### Additional differences requiring targeted review, not wholesale adoption

| Area | Upstream change | Cloakfox status / decision |
|---|---|---|
| Cross-process font/voice lists | Lists stored in shared storage and reconstructed in each process. | Font configuration already has owner snapshots, epoch invalidation and worker coverage in Cloakfox. `SpeechVoicesManager` still has a process-local map; ordinary personas block native voices and may bypass this path. Verify custom setter-driven lists across processes before calling this an active leak. |
| Storage timing and session lifetime | Miss cache avoids repeated synchronous reads for absent values; launch-only state uses default prefs and worker-safe mirrors. | Cloakfox has worker-safe snapshots and authoritative refresh for large persistent persona configs. Do not replace persistent identity preferences with launch-only default prefs. Measure missing-key lookup costs and consider a correctly invalidated miss cache only if a gap is demonstrated. |
| WebRTC consistency | Revised candidate/statistics consistency and OS-aware port behavior, with substantial synthetic candidate logic. | Cloakfox lacks these specific helpers but has native relay/proxy privacy policy and real-media requirements. This is a compatibility/design review, not an approved import; fabricated network details do not prove actual routing privacy. |
| Screen available rectangle | Protection precedence and context OS are considered instead of only physical host metrics. | Cloakfox uses different content letterboxing and screen controls. Compare policy/exception combinations and stock Firefox before porting; direct replacement would discard Cloakfox behavior. |
| Media devices / codecs | New fake-device backing and decoder-reporting overrides. | Already listed above. Different behavior, but fake capture or support claims without playback can undermine daily-use compatibility. |

### Already covered / not additional missing work

- Explicit `Intl.Locale` language/script/region values are preserved in Cloakfox
  155; the global low-level locale override is disabled in favor of document/worker
  paths. Upstream’s explicit-locale fix should not be counted as missing.
- Font fallback/system-ui/CSS2 ownership, glyph-position preservation, touch
  coherence and native voice-registration suppression were previously adapted.
- Privileged setter gates and Firefox UA branding already exist with Cloakfox’s
  architecture; upstream’s Juggler sealing lifecycle is a different implementation.
- Trusted automation input, hidden debugger behavior and driver popup bypasses
  are automation features, not privacy patches to import by default.

The four source findings above have been added to TODO. They require native
regressions and preservation of site/container isolation before implementation
can be described as verified.
