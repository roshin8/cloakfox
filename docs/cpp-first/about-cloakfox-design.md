# about:cloakfox — settings page design

**Branch:** `cpp-first-exploration`
**Status:** exploration, not implementation
**Date:** 2026-04-21

## Why a native settings page

Today the extension popup is the only UI. It talks to background, which
talks to the content script, which calls WebIDL setters — three hops
and a lot of ceremony. If Cloakfox owns the browser, it can register a
native `about:` page that reads and writes prefs directly with parent-
process authority, and the extension UI shrinks to nothing (or
disappears entirely).

## Registration mechanism

Firefox exposes `about:` URIs via `nsIAboutModule` components. Register
one via `manifest` entry:

```
component {<uuid>} AboutCloakfox.sys.mjs
contract @mozilla.org/network/protocol/about;1?what=cloakfox {<uuid>}
category about-module cloakfox @mozilla.org/network/protocol/about;1?what=cloakfox
```

The module returns a `chrome://cloakfox/content/settings.html` URI
when the browser navigates to `about:cloakfox`. The HTML is shipped
via a `chrome.manifest` content registration:

```
content cloakfox jar:cloakfox.jar!/content/
```

Flags to request on the AboutModule:
- `URI_SAFE_FOR_UNTRUSTED_CONTENT` — OFF (we want system principal).
- `ALLOW_SCRIPT` — ON (obviously).
- `IS_SECURE_CHROME_UI` — ON (grant pref-write privileges).
- `ENABLE_INDEXED_DB` — OFF (no need).

With `IS_SECURE_CHROME_UI`, scripts inside the page can:
- `Services.prefs.setCharPref(...)` / `setIntPref(...)` directly,
  writing to the parent-process prefs DB. This is exactly the
  capability the extension popup *doesn't* have, and the reason
  `setHttp2Profile` was a silent no-op from content scope.
- `Services.cpmm` message-manager APIs to coordinate with content
  processes if we want live-reload behavior.

## UI framework

Option A — vanilla HTML + a single `settings.js` chrome-privileged
script. Simplest. ~500 lines for the current popup feature set.

Option B — React + Tailwind bundled via esbuild (same toolchain as
today's popup). Heavier, but if we're porting existing popup code it's
a lift-and-shift.

**Recommendation:** A. The popup's current density is modest (6 tabs,
mostly toggle lists and dropdowns). Rewriting in 500 lines of vanilla
HTML gets us something faster, no framework CVE surface, and no
bundler in the Cloakfox build pipeline.

## Pref schema

User-visible prefs live under `cloakfox.*` namespace:

```
cloakfox.enabled                    bool    master kill-switch
cloakfox.http2.profile              string  firefox|chrome|safari
cloakfox.http3.profile              string  firefox|chrome|safari
cloakfox.fingerprint.level          string  strict|balanced|permissive
cloakfox.canvas.mode                string  off|noise|block
cloakfox.webgl.mode                 string  off|noise|block
cloakfox.audio.mode                 string  off|noise|block
cloakfox.navigator.ua_profile       string  auto|firefox|chrome|safari
cloakfox.fonts.allowlist            string  comma-separated
cloakfox.speech.mode                string  off|hide|spoof
cloakfox.containers.mode            string  global|per-container
cloakfox.webrtc.ip_policy           string  default|disable_non_proxied
cloakfox.math.noise_magnitude       int     default 13 (exponent of 1e-N)
cloakfox.keyboard.cadence           bool    default true
cloakfox.monitor.enabled            bool    default true
```

Per-container overrides go under `cloakfox.container.<userContextId>.<key>`.
The C++ manager lookup walks the chain:
`per-container → global → hardcoded default`, same as Firefox's own
permission model.

## Per-container config storage

Two paths, pick one:

### Path 1: prefs-only (lean)

All per-container settings live as `cloakfox.container.<id>.<key>` prefs.
Pro: no new storage layer; pref observer gives live updates for free;
backup via profile sync.
Con: prefs DB gets cluttered (~15 keys × N containers).

### Path 2: json file (cleaner)

A `cloakfox.json` in the profile dir holds `{containers: {id: {settings}}}`.
RoverfoxStorageManager picks up changes via `nsIFileChangeObserver`.
Pro: tidy; easy to diff and version.
Con: new IO path, new consistency story, worse for roaming profiles.

**Recommendation:** Path 1. Firefox profiles already carry hundreds of
prefs; a few per container doesn't move the needle, and pref observers
are battle-tested. Revisit only if per-container config gets really
large (e.g. per-container font allowlist of 1000s of entries).

## C++ read path

Managers already key on `mUserContextId`. Extension today calls
`setXxx(seed)` WebIDL setters to seed them. In cpp-first:

1. At nsGlobalWindowInner construction, a new `CloakfoxConfigLoader`
   reads the per-container pref subtree for this userContextId and
   pushes it into `RoverfoxStorageManager` (the already-built storage
   layer C++ managers read from).
2. First `.getParameter()` / `.toDataURL()` / etc. call sees the
   seeded state and produces the spoofed value.
3. Pref observer: when about:cloakfox writes a new value,
   `CloakfoxConfigLoader` re-reads and bumps a generation counter so
   future window constructions pick up the change. (Live-reload in an
   already-loaded tab requires forcing window-reconstruction or
   publishing to existing windows — not v1.)

No extension involved. No WebIDL setter round-trip. No `[Func="..."]`
gate. No documentElement bridge. No stealth concerns — about:cloakfox
is a chrome page, not visible from page context.

## Bundled extension — what's left

Two options:

### Option A: zero extension

All spoofer logic moves to C++ + a privileged JS frame script (see
`frame-script-pattern.md`). UI is about:cloakfox. The `cloakfox-shield`
extension is removed.

### Option B: tiny extension for the popup toolbar icon

Some users prefer a toolbar icon that opens the settings page. That
can be a 30-line extension: a single browser action whose click
handler calls `browser.tabs.create({url: "about:cloakfox"})`. No
content scripts, no background logic, no inject code. Still shows up
in about:addons as "Cloakfox Shield" but has no elevated permissions.

**Recommendation:** B. The toolbar access is a real UX win and the
cost is negligible. But the extension stops doing any fingerprint
work — it's purely a launcher.

## What this simplifies vs. today

| Moving part today | cpp-first equivalent |
|---|---|
| Extension background/header-spoofer.ts | Gone — prefs drive C++ which drives headers |
| core-bridge.ts + callOrAlreadyConfigured() | Gone — no WebIDL setters to skip-coordinate |
| cloakfoxIsConfigured() WebIDL | Gone — nothing to query |
| IsCloakfoxShieldCaller principal gates | Gone — no callable WebIDL |
| documentElement bridge + ISOLATED/MAIN dance | Gone — no cross-world coordination |
| Phase 3 exportFunction migration | Irrelevant — no MAIN-world JS |
| Experiment API for http2Profile | Gone — prefs work directly |
| preCoreHandled Set + per-signal skip logic | Gone — C++ owns the state |

## What this does NOT simplify

- The C++ patches themselves. We still ship 62 patches. In fact the
  cpp-first direction might *add* ~3-5 small patches (pref-loader,
  about:cloakfox registration, frame-script loader plumbing).
- The JS spoofers that can't move — see inventory.md for the list.
  They become a privileged frame script, not disappear.
- The build pipeline — Firefox source, patches, mach build. Same.

## Known unknowns

- Live-reload of open tabs when pref changes: probably needs a
  content-process observer that pokes RoverfoxStorageManager. Non-v1.
- Profile-sync interaction with `cloakfox.container.<id>.*` prefs —
  if users sync across machines with different container sets, what
  happens? Probably needs sync-exclude.
- Cloakfox-mode vs. Firefox RFP (`privacy.resistFingerprinting`) — we
  currently force RFP off. Settings page should hide/disable it to
  avoid double-spoofing.
- Extension signing — if we keep option B (thin launcher extension),
  signing cost is trivial. If we keep the current rich extension as a
  fallback path, signing stays complex.

## Next steps

1. Wait for `inventory.md` (in-flight agent) to enumerate what JS can
   and cannot move.
2. Prototype the C++ pref-reader at `nsGlobalWindowInner`
   construction using an existing simple spoofer (e.g. canvas seed).
   One patch, one test.
3. Stub `about:cloakfox` with a single toggle wired to
   `cloakfox.enabled`. Prove the chrome-privileged pref-write path
   works end-to-end.
4. If (2) and (3) look clean, write a migration RFC: what changes in
   the extension, what patches get added, order of operations.
