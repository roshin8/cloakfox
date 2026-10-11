# Daily-driver privacy implementation — Firefox 155

Implemented in the existing `codex/firefox-155-compat` worktree. The original
checkout was not changed by this work. Changes remain uncommitted and unmerged.

## Delivered

| Area | Result |
| --- | --- |
| Engine identity | Generated DOM/HTTP UA follows Firefox 155; stored legacy personas migrate without rotating seeds or losing explicit overrides. |
| Everyday defaults | HTTPS-Only and protective Safe Browsing preferences; everyday user choices persist across restarts; native controls remain accessible. |
| Container forgetting | Explicit destructive action separate from appearance changes; target tabs, cookies, IndexedDB, Cache API and workers clear; current and fallback session records are pruned with strict persistence error reporting. Shared data/ambiguous permissions are retained. |
| Network controls | Per-container required proxy and blocked modes; native callback cancels bypass/direct fallback; native RTC disabled/relay policy and route-change closure; public-IP echo requires opt-in. |
| Site isolation | HMAC keys from the full container secret and Gecko top-level schemeful site; propagated across frames/workers, canvas, WebGL, audio, Math and layout/font caches. |
| Blocking | Pinned official signed uBlock Origin bundled, normal updates and site controls retained; disable/removal persists. |
| Container workflows | Exact-host native rules, explicit routing toggle, temporary container last-tab/whole-window cleanup and startup recovery. |
| Backups | Password-encrypted named-container settings export/import into fresh IDs with validation/conflict handling; native full-profile backup settings offered when available. |
| Releases | Offline signed metadata verification and visible build/provider readiness. Production updater remains disabled pending real configuration. |

Letterboxing reconciled in the preceding port work remains included and passes
its live geometry/fullscreen checks.

## Verification

- Native macOS arm64 build: **passed** (`build-4.log`, following full compilation in build 3 and its corrected reference-ownership error).
- Fresh Firefox 155 patch stack: **80/80 applied**, no failures (`stack-3.log`).
- Patched source equality: **183/183 files match** the fresh patch result (`source-verification.json`).
- Non-patch diff whitespace check: **passed**. Raw patch-file diffs contain required unified-diff context prefixes, which Git flags as trailing whitespace.
- Addition/settings mirror equality: **48/48 match** (`addition-verification.json`).
- Node behavioral tests: **100 passed, 0 failed, 0 skipped** (`node-all.log`).
- Release verification: **11 passed**; blocker staging: **6 passed**; native RTC decision helper: **1 passed**.
- Compiled WebGL/canvas/worker-cache helpers: **5 passed**; scoring self-test passed.
- New daily-driver live suite: **10/10 passed** (`verified-runtime-results.json`).
- Existing compatibility probes: **13/13 passed**, plus **4 HTTP/3 preference tests** (`compat-runtime/final-runtime-results.json`).

The real routing probe verifies a working proxy, refused proxy, native bypass
rejection, default/named-container blocking, malformed preference rejection and
unaffected system background traffic. The local WebRTC probe has a working STUN
positive control and observes zero direct packets in relay mode, including after
a page requests `iceTransportPolicy: all`.

The live forgetting probe reads the actual IndexedDB marker rather than relying
on database enumeration; it verifies target removal and control-container data
retention for both default and named containers. Shared permission boundaries
have a separate passing live probe. Workflows are tested through native routing,
an encrypted file roundtrip, fresh imported IDs, last-tab and whole-window
closure, and persisted startup recovery. The native backup settings entrypoint
is available on this build; a full native profile archive/restore was not tested.

Older actor/WebGL tests now use a real stable local site, and repeated-identity
WebGL runs fix the complete master secret. This preserves their behavioral
assertions while testing the new site-keyed identity contract.

## Remaining production requirements and limits

- **Automatic browser updates:** owner-controlled release signing keys/trust root,
  hosting and deployment are not configured. Do not enable Mozilla test update
  certificates. Offline metadata verification does not constitute an installed
  automatic updater. See `updates.md` for the concrete release procedure.
- **Safe Browsing:** this build lacks the Google provider key. Preferences are on,
  but those provider lists are unavailable. The settings page reports this.
- **Platform coverage:** the native build/runtime checks here are macOS arm64.
  Linux/Windows packaging and runtime remain CI/release validation work.
- A required route governs new page requests; existing downloads may continue.
  Content preference IPC/transport shutdown is asynchronous. This is not a VPN
  kill switch, and a proxy alone is not a full anonymity system.
- Native site routing deliberately preserves opener/named-target exceptions;
  the UI states this. Full profile backup uses Firefox’s separate workflow;
  encrypted identity-settings exports exclude cookies, passwords and history.
- Restore is validated and rolls back failed imports with persistence/error
  reporting, but is not a crash-atomic transaction. External backup copies and
  OS snapshots are outside container forgetting.
- Broad persona fields remain container-scoped. The site noise work is not a
  guarantee that every fingerprint surface or opaque/service-worker context is
  unlinkable; detailed runtime coverage is recorded in `site-isolation.md`.

## Implementation decisions

The accepted audit was treated as approval for reversible implementation in the
existing worktree. Production updates stay disabled without a real trust root;
shared permissions stay intact where historical ownership is ambiguous;
identity-settings backup is explicitly distinct from full-profile backup; and
required-proxy requests fail instead of becoming direct when Firefox applies a
native bypass. These choices and their tradeoffs are recorded in `progress.md`.

See the individual implementation/review reports in this directory for code
ownership, failure cases, and exact test commands.


## Subsequent Camoufox fixes

The September 7 upstream hardening adds a final patch (81 total), content-only
font filtering, glyph-position preservation, chrome-only RTC setters, coherent
touch APIs/CSS, voice registration protection, and a SessionStore guard. See
[the implementation and verification report](camoufox-upstream-hardening.md).
Earlier counts above describe the preceding daily-driver implementation snapshot.
