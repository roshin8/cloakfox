# Camoufox upstream hardening — 2026-09-07

Implemented in the Firefox 155 compatibility worktree, branch
`codex/firefox-155-compat`. The original checkout was not edited. Changes remain
uncommitted and unmerged.

Upstream reference: [Camoufox snapshot eb5dc3b](https://github.com/daijro/camoufox/tree/eb5dc3bc5b917d1e6c71d9cacfecdddb55fbfc4a/patches).
The source targets Firefox 152; these changes adapt the relevant behavior to
Firefox 155.0.1 and Cloakfox's container/site isolation. The new
`patches/cloakfox-upstream-hardening.patch` applies after site fingerprint isolation.

## Changes

- **Glyph positioning:** noise changes only x/y advances. HarfBuzz positioning
  offsets are preserved, including combining-mark attachment positions, in both
  horizontal and vertical shaping. Existing site-derived spacing seeds remain.
- **Font isolation:** retire the persisted process-wide font whitelist. Filter
  content lookups using each provider's container snapshot, preserve native chrome
  and internal font access, and retain the conservative content startup set until
  a persona exists. Filter common/global fallback and force the cmap path for
  protected content; prevent `src: local()` from bypassing the mask. Do not reuse
  the global replacement-character cache or publish container-specific misses
  into the shared no-font cache. System-ui and CSS2 system fonts use the owning
  container; CSS2 spoofing moves out of the Cocoa native-font service into the
  document-aware cross-platform path. Protected generic/emoji resolution returns
  an owned, freshly resolved list; it never reuses the chrome/global cache.
  Last-resort font selection and font-group scans are filtered too. If a mask
  names no installed fonts, layout uses the fixed bundled Arial family instead
  of an arbitrary host family. Environment-only font lists remain supported;
  that fallback reads the environment JSON directly and skips nonstring entries.
- **Setter protection:** WebRTC IPv4/IPv6 setters are ChromeOnly WebIDL methods.
  Remove page-property deletion and use the privileged actor's Xray window view.
  Other existing caller-gated setters retain their restrictions.
- **Touch coherence:** preserve a fine/hovering desktop primary pointer, add coarse
  capability to any-pointer for a configured digitizer, and expose Touch/TouchEvent
  accordingly without enabling legacy page ontouch handlers. Respect RDM override
  precedence. Remove the actor's obsolete pointer/hover pins so JS queries use the
  same native result as stylesheet media queries. Use Cloakfox's existing
  `navigator:maxTouchPoints` key.
- **Voice registration:** an explicitly configured upstream voice list prevents
  native host voice registration, including an empty list or entries with missing
  required fields. An explicit false blocking flag is honored when no list exists;
  the prior optional-value presence check mistakenly treated false as blocking.
- **SessionStore:** ignore windows without a tracked session record before marking
  tabs not to restore. Tracked windows retain the original behavior.

## Verification

- macOS arm64 Firefox native build passed (`upstream-build-5.log`). Two prior
  compile iterations corrected the document chrome-check API and typed enum
  inference; the final build reported zero compiler warnings.
- New native behavioral tests: 5 passed (`upstream-unit-green.log`). The original
  glyph, voice and SessionStore behavior failed the corresponding assertions
  before implementation (`upstream-unit-red.log`). The generic/emoji cache test
  also fails against the pre-fix source (`upstream-font-cache-red.log`).
- Node suite: 102 passed, no failures/skips (`upstream-node-all.log`). New media
  query regression first failed against the actor's old pins
  (`upstream-mediaquery-red.log`).
- Expanded browser coverage passed (`upstream-runtime-final.log`), including a
  restrictive Arial-only container and a real voice-registry sentinel control.
  Initial live failures were recorded in `upstream-runtime-red.log`.
- Existing native WebRTC policy, site isolation, container workflows, and settings
  UI probes: 4/4 passed (`upstream-reviewed-runtime/results.json`). Local STUN positive
  control received five packets; relay-only received zero.
- Final fresh patch stack: 81/81 applied; all 189 checked source files match the
  built checkout (`upstream-stack-final.log`, `upstream-source-verification.json`).

Tests use disposable profiles and local pages. Glyph tests exercise the actual
native shaping loop but do not replace visual QA across multilingual font packs.
Linux and Windows have not been compiled or run locally. The SessionStore check
reproduces an untracked-record exception by executing the real method; it does not
claim a normal browsing crash was reproduced. No automatic updates, automation
input trust changes, or upstream UI-removal patches were added.


## Independent review

The review found three additional gaps exposed by removing the global whitelist:
last-resort fallback, generic/emoji cache sharing, and environment font-list
compatibility. All three were addressed. The restrictive live probe reproduced
`Academy Engraved LET` outside an Arial-only mask before correction
(`upstream-font-review-red.log`); the final run renders Arial for explicit,
missing-family, and system-ui requests. The final read-only review found no
remaining blockers in the changed fallback/cache paths.

A packaged font pack containing Arial is part of the emergency metric fallback
assumption. This fallback is used only when the configured list has no installed
family; it prevents an invalid mask from selecting a host-dependent default or
leaving layout without metrics. No claim is made that arbitrary invalid font
configurations can be rendered exactly as requested.
