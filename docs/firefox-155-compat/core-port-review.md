# Independent review of the 19 core Firefox 155 ports

Reviewed the original patch additions, the regenerated patches, and their
resolved Firefox 155.0.1 source snapshots. Scope was regressions introduced by
the version port, including missing adaptations to changed upstream APIs.
Pre-existing spoofing behavior was not treated as a new finding. No patches or
Firefox sources were changed during this review.

## Finding: Linux Mozilla native-manifest lookup must force the legacy home

**Priority: P2. Status: fixed by the integrating task and rechecked.**

In `librewolf/mozilla_dirs.patch`, the added `XRE_MOZ_USER_NATIVE_MANIFESTS`
branch initially retained the old two-argument call to
`GetUserDataDirectoryHome(file, false)`. Firefox 155 adds XDG home resolution;
upstream explicitly passes `aForceLegacy = true` for native-manifest lookup.
Without matching that argument in the added Mozilla compatibility branch, a
fresh Linux profile using XDG resolution searches beneath the config home and
appends `.mozilla`, rather than finding native messaging manifests installed
beneath `~/.mozilla`. Existing legacy profiles can conceal this regression.

The integrating task added `/* aForceLegacy */ true` to the Mozilla branch and
regenerated the patch. Reinspection confirms that both the LibreWolf and Mozilla
user-native-manifest branches now force the same legacy home while preserving
their distinct suffixes. The integrating task reported exact application
verification after regeneration. Runtime Linux directory-service/native-host
lookup was not exercised by this review.

## Coverage and other conclusions

No other concrete port-introduced semantic or compile defect was identified in
the reviewed changes. This does not replace full compilation or runtime checks.

| Patch | Focus and result |
| --- | --- |
| `audio-fingerprint-manager` | Manager export and separate compilation remain at build-file top level. AudioNode/AudioContext parent accessors still support the window/context lookup used by the added hooks. |
| `codecs-spoofing` | MIME override remains in `CanPlayType`; current function arguments and string APIs match the existing hook. Media-element include path is preserved. |
| `config` | Configuration files remain installed from `lw` and listed in the package manifest outside the preceding Windows-only block. Root build traversal includes `lw`. |
| `cross-process-storage` | Both messages remain parent-directed synchronous IPDL calls, with matching receiver declarations, implementations, and sync-message entries. Namespaced preference checks and return-value flow are retained. |
| `font-hijacker` | Port removes the updated `mImpl->Load()` call rather than preserving the obsolete error argument. The new `UpdateOwnerKeepAlive()` call remains. Status notification/promise updates surrounding the override are preserved. |
| `font-list-spoofing` | Per-context guards and lookup filtering remain at their corresponding sites. `FontFaceSet` still obtains `GetOwnerWindow()` through `DOMEventTargetHelper` / `GlobalTeardownObserver`, so this apparent accessor migration does not require another change. |
| `geolocation-spoofing` | Real-location fallback uses Firefox 155's `fetchLocation` and `lazy.log.info` APIs. The constructed position remains available to listener and cache updates; upstream retry/backoff logic remains after the branch. |
| `http2-fingerprint-spoofing` | Existing SETTINGS construction, connection-level profile propagation, and HPACK pseudo-header ordering survive the rebase. Current socket origin-attribute lookup and constructor-independent flow are retained. |
| `indexeddb-spoofing` | Promise creation is adapted to `GetRelevantGlobal()`, matching Firefox 155's adjacent native code and existing early liveness check. |
| `locale-spoofing` | Added methods and backing subtag members retain their prior signatures and placement. Locale initialization is inserted after the current tab-bar visibility update; native locale fallback remains present. |
| `network-patches` | Current `SetAcceptEncodings` dictionary argument and all downstream secure/dictionary assignment branches are preserved. The temporary override string remains alive through copying into the destination. |
| `permissions-spoofing` | Override remains in the conversion used by initialization and browser-permission changes. Firefox 155's new system-permission state cannot override the spoofed `Prompt`, because `State()` consults that state only when browser state is `Granted`. |
| `shadow-root-bypass` | Alias now maps to `GetOpenOrClosedShadowRoot(nsIPrincipal&)` and supplies `NeedsSubjectPrincipal`, matching the current native accessor and upstream exposed property. |
| `storage-estimate-spoofing` | Both promise paths use the new `mGlobal` member, and native execution still uses the current main/worker helper when no override applies. |
| `webrtc-ip-spoofing` | Stats sanitization is inside the new unconditional asynchronous GetStats continuation and captures the container ID/profile decision. SDP sanitization, candidate hooks, and both committed/uncommitted JSEP default-candidate updates remain. New upstream state handling is retained. |
| `cpp-first-error-stack-depth` | Constant moved to `vm/ErrorObject.h`. Current `GetStackTraceLimit()` uses it both as fallback and upper bound, including the experimental configurable stack-limit path. |
| `cloakfox-optional-assets-car` | Asset selection moved to the current `MacOSBundle` extra-file list. Configure checks the actual branding directory for `Assets.car`; icon resources and updater handling remain intact. |
| `librewolf/dbus_name` | Client/server bus names, object paths, interfaces, and fallback names agree. Firefox 155's GDBus validation and invocation code is preserved. |
| `librewolf/mozilla_dirs` | Fixed the missing legacy-home argument described above; system/user Mozilla compatibility directories and native-manifest lookup entries remain paired. |

## Validation limits

Python AST parsing passed for all 18 changed build/configure files across these
ports. `node --check` passed for all three changed JavaScript files. Modified
source files contained no unresolved merge markers. C++ accessors and relevant
inheritance/consumer declarations were inspected, but generated bindings, IPDL
code, C++ linking, platform packaging, and browser runtime were not built or run
as part of this independent review.

The asset-catalog package-manifest entry remains unconditional, as it was before
the port; this is inherited packaging behavior rather than a new finding from
the `MacOSBundle` migration. Similarly, broader pre-existing fingerprint
coherence or lifetime concerns were excluded from the findings above.
